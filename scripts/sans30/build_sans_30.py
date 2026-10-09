#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Friday Sans / Sans UI 3.0 -- soften the 2.5 faces.

    python build_sans_30.py --src work/sans-3.0/x/FridaySans-2.5/ttf --out work/sans-3.0/ttf

2.5 was hinted for Windows (ttfautohint for the Latin, Chlorophytum for kana and
kanji).  Every stem is snapped to whole pixel rows there, so small text looks
hard.  Unhinted it looks soft but also thin.  3.0 therefore

  1. rounds sharp ink corners (a short quadratic fillet, so a pointed stroke end
     stays pointed instead of being eroded by a morphological opening),
  2. widens every stem a little (offset outwards, round joins) to give back the
     density that Mac's stem darkening gives for free,
  3. drops all hinting and sets gasp to smoothing only, so GDI / DirectWrite /
     WPF draw the outline as it is, as Mac does.

The widening is searched per glyph: where the offset would close a counter or a
gap (contour count changes, or the area grows less than a clean offset would),
the amount is bisected down until the glyph is intact.

Also fixed on the way: usWin* identical in all weights of a family, vendor ID,
em/en space widths, lsb / tsb of every glyph, version strings.
"""
import argparse
import glob
import json
import os
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pathops  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402
from fontTools.ttLib.tables import ttProgram  # noqa: E402
from fontTools.pens.ttGlyphPen import TTGlyphPen  # noqa: E402
from fontTools.pens.cu2quPen import Cu2QuPen  # noqa: E402
from fontTools.pens.recordingPen import RecordingPen  # noqa: E402
import soften as S  # noqa: E402

VERSION = "3.001"
VENDOR = "FRDY"
# Sans UI 2.5 drew its glyphs for em 1050, i.e. the kanji face was 0.850 em, smaller than
# Yu Gothic UI (0.875), Meiryo UI (0.870) and Noto Sans JP (0.880).  3.0 reads the same
# outlines as em 1010 (kanji face 0.884) and rescales to upem 1000.
UI_EM_OLD, UI_EM_NEW = 1050, 1010
UPEM = 2000
UI_LINE = (2014, -501)  # 2.5's 1017 / -253 (em 1050) re-read as em 1010 at upem 2000: covers what 2.5 covered
# kanji vertical stem (units per 1000) from reports/weight-audit.json
STEM = {"Light": 49.0, "Regular": 64.0, "Medium": 78.5, "SemiBold": 87.0, "Bold": 100.0}
K_CONVEX, K_CONCAVE, K_EMBOLDEN = 0.19, 0.09, 0.039
# Dense glyphs get less widening.  The same offset on every glyph makes a many-stroke kanji
# (whose strokes and gaps are already thin) look darker than a simple one.  r = ink area of
# the glyph / median ink area of the kanji in the same face (2.5 outline); the offset is full
# up to r = DENSE_START and falls linearly to DENSE_FLOOR x e at r = DENSE_END.
DENSE_START, DENSE_END, DENSE_FLOOR = 1.00, 1.15, 0.15


def to_working_em(f, ui):
    """Sans UI: read the 2.5 outlines as em 1010.  Both: upem 2000, so that an offset of
    2.5 units in 1000-space is a whole number of font units and survives rounding."""
    from fontTools.ttLib.scaleUpem import scale_upem
    if ui:
        assert f["head"].unitsPerEm == UI_EM_OLD
        f["head"].unitsPerEm = UI_EM_NEW
    scale_upem(f, UPEM)


def density_factor(r):
    if r <= DENSE_START:
        return 1.0
    t = min(1.0, (r - DENSE_START) / (DENSE_END - DENSE_START))
    return 1.0 - (1.0 - DENSE_FLOOR) * t


def ink_areas(f):
    """Absolute ink area per glyph (font units^2, the glyph as drawn), and the median over kanji."""
    from fontTools.pens.areaPen import AreaPen
    gs = f.getGlyphSet()
    area = {}
    for n in f.getGlyphOrder():
        if f["glyf"][n].numberOfContours == 0:
            continue
        pen = AreaPen(gs)
        gs[n].draw(pen)
        area[n] = abs(pen.value)
    cm = f.getBestCmap()
    kanji = sorted(area[cm[cp]] for cp in range(0x4E00, 0xA000) if cp in cm and cm[cp] in area)
    return area, kanji[len(kanji) // 2]


def weight_of(name):
    for w in ("SemiBold", "Light", "Medium", "Bold"):
        if "-" + w in name:
            return w
    return "Regular"


def seg_path(cons):
    p = pathops.Path()
    pen = p.getPen()
    for segs in cons:
        pen.moveTo(segs[0][1])
        for s in segs:
            if s[0] == "l":
                pen.lineTo(s[2])
            else:
                pen.qCurveTo(s[2], s[3])
        pen.closePath()
    return p


def perimeter(path):
    rp = RecordingPen()
    path.draw(rp)
    tot = 0
    cur = st = None
    for op, args in rp.value:
        if op == "moveTo":
            cur = st = args[0]
        elif op == "lineTo":
            tot += S._len(cur, args[0])
            cur = args[0]
        elif op == "qCurveTo":
            pts = list(args)
            if pts[-1] is None:
                return None
            for i in range(len(pts) - 1):
                nxt = pts[-1] if i == len(pts) - 2 else S._lerp(pts[i], pts[i + 1], 0.5)
                tot += S._seglen(("q", cur, pts[i], nxt))
                cur = nxt
        elif op == "curveTo":
            tot += sum(S._len(a, b) for a, b in zip([cur] + list(args[:-1]), list(args)))
            cur = args[-1]
        elif op in ("closePath", "endPath"):
            tot += S._len(cur, st)
    return tot


def offset_path(fill, e):
    if e <= 0:
        return fill
    st = pathops.Path(fill)
    st.stroke(2 * e, pathops.LineCap.BUTT_CAP, pathops.LineJoin.ROUND_JOIN, 4)
    st.convertConicsToQuads(0.1)
    st.simplify(fix_winding=True, keep_starting_points=False, clockwise=True)
    return pathops.op(fill, st, pathops.PathOp.UNION, fix_winding=True,
                      keep_starting_points=False, clockwise=True)


def tt_glyph(path):
    tt = TTGlyphPen(None)
    path.draw(Cu2QuPen(tt, 0.4, reverse_direction=False))
    return tt.glyph()


def quantized(path):
    """The outline as it will be stored: quadratic, integer coordinates, overlaps resolved."""
    g = tt_glyph(path)
    p = pathops.Path()
    g.draw(p.getPen(), None)
    p.simplify(fix_winding=True, keep_starting_points=False, clockwise=True)
    return p


def widen(cons, e):
    """Return (TrueType glyph, e actually used).  Bisect e until the offset is clean."""
    base = seg_path(cons)
    base.simplify(fix_winding=True, keep_starting_points=False, clockwise=True)
    a0, n0, P = abs(base.area), len(list(base.contours)), perimeter(base)

    def clean(x):
        if x <= 0:
            return base, True
        try:
            out = offset_path(base, x)
        except pathops.PathOpsError:      # Skia could not resolve this offset: treat as unclean
            return base, False
        q = quantized(out)       # integer rounding can fuse two contours that are 1 unit apart
        grown = (abs(out.area) - a0) / P if P else x      # mean offset actually achieved
        # 15 % of x, but never tighter than half a unit: integer rounding alone moves a small x
        return out, len(list(q.contours)) == n0 and abs(grown - x) <= max(0.15 * x, 0.5)

    out, ok = clean(e)
    used = e
    if not ok:
        lo, hi = 0.0, e
        best, _ = clean(0)
        for _ in range(5):
            mid = (lo + hi) / 2
            o, good = clean(mid)
            if good:
                lo, best = mid, o
            else:
                hi = mid
        out, used = best, lo
    return tt_glyph(out), used


def strip_hints(f):
    for t in ("fpgm", "prep", "cvt "):
        if t in f:
            del f[t]
    for n in f.getGlyphOrder():
        g = f["glyf"][n]
        if hasattr(g, "program"):
            p = ttProgram.Program()
            p.fromBytecode(b"")
            g.program = p
    m = f["maxp"]
    m.maxSizeOfInstructions = m.maxStorage = m.maxFunctionDefs = 0
    m.maxInstructionDefs = m.maxTwilightPoints = m.maxStackElements = 0
    m.maxZones = 1
    f["gasp"].gaspRange = {0xFFFF: 0x000A}      # smoothing only, no grid fitting


def count(cons):
    p = seg_path(cons)
    p.simplify(fix_winding=True, keep_starting_points=False, clockwise=True)
    return len(list(p.contours))


def build_one(args):
    src, dst = args
    base = os.path.basename(src)[:-4]
    weight = weight_of(base)
    f = TTFont(src)
    to_working_em(f, "SansUI" in base)
    scale = f["head"].unitsPerEm / 1000.0
    stem = STEM[weight] * scale
    dv, dc, e = K_CONVEX * stem, K_CONCAVE * stem, K_EMBOLDEN * stem
    gs, glyf = f.getGlyphSet(), f["glyf"]
    areas, kanji_median = ink_areas(f)
    old = {}
    for n in f.getGlyphOrder():
        g = glyf[n]
        old[n] = g.yMax if g.numberOfContours != 0 else None
    vorg = {n: f["vmtx"][n][1] + old[n] for n in old if old[n] is not None}
    reduced = {}
    lighter = {}
    kept_sharp = []
    failed = []
    t0 = time.time()
    for n in f.getGlyphOrder():
        if glyf[n].numberOfContours <= 0:
            continue
        try:
            cons = S.contours_from(gs, n)
            soft = [S.soften_contour(c, dv, dc) for c in cons]
            if count(soft) != count(cons):      # e.g. squares touching at a corner: keep as drawn
                soft = cons
                kept_sharp.append(n)
            e_n = e * density_factor(areas[n] / kanji_median)
            glyf[n], used = widen(soft, e_n)
            if e_n < e and used < 0.5 * e_n:
                # a small offset can fail where the full one succeeds (rounding splits a thin join
                # that the full offset heals): fall back to the full amount for this glyph
                glyf[n], used = widen(soft, e)
                e_n = e
        except pathops.PathOpsError:
            failed.append(n)                    # leave the 2.5 outline (hints are stripped below)
            continue
        if e_n < e:
            lighter[n] = round(e_n, 3)
        if used < e_n:
            reduced[n] = round(used, 3)
    strip_hints(f)
    # lsb / tsb follow the new outlines
    hmtx, vmtx = f["hmtx"], f["vmtx"]
    for n in f.getGlyphOrder():
        g = glyf[n]
        if g.numberOfContours == 0:
            continue
        g.recalcBounds(glyf)
        hmtx[n] = (hmtx[n][0], g.xMin)
        if n in vorg:
            vmtx[n] = (vmtx[n][0], vorg[n] - g.yMax)
    # em / en spaces: the Inter widths drift with weight; make them what the names say
    cm = f.getBestCmap()
    upem = f["head"].unitsPerEm
    for cp, w in ((0x2000, 500), (0x2001, 1000), (0x2002, 500), (0x2003, 1000)):
        n = cm.get(cp)
        if n:
            hmtx[n] = (round(w * upem / 1000), 0)
    if "SansUI" in base:
        f["hhea"].ascent, f["hhea"].descent, f["hhea"].lineGap = UI_LINE[0], UI_LINE[1], 0
        o = f["OS/2"]
        o.sTypoAscender, o.sTypoDescender, o.sTypoLineGap = UI_LINE[0], UI_LINE[1], 0
    f["OS/2"].achVendID = VENDOR
    f["head"].fontRevision = float(VERSION)
    name = f["name"]
    fam = "Friday Sans UI" if "UI" in base else "Friday Sans"
    for r in list(name.names):
        s = r.toUnicode()          # Mac (platform 1) records too: the unique ID there stayed 2.500
        if r.nameID == 5:
            name.setName("Version " + VERSION, 5, r.platformID, r.platEncID, r.langID)
        elif r.nameID == 3 and s:
            name.setName(s.replace("2.500", VERSION), 3, r.platformID, r.platEncID, r.langID)
        elif r.nameID == 10 and s:
            name.setName("%s %s: proportional Japanese text face (Inter + Noto Sans CJK JP + "
                         "hand-drawn kana). 3.0 softens 2.5: rounded corners, slightly fuller "
                         "stems, no hinting." % (fam, VERSION[:3]),
                         10, r.platformID, r.platEncID, r.langID)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    f.save(dst)
    return base, dict(dv=round(dv, 2), dc=round(dc, 2), e=round(e, 2), reduced=reduced, lighter=len(lighter), kept_sharp=kept_sharp, failed=failed,
                      seconds=round(time.time() - t0, 1))


def unify_win_metrics(paths):
    """usWinAscent / usWinDescent: the same in every weight of a family, covering all of them."""
    fams = {}
    for p in paths:
        fams.setdefault("UI" if "SansUI" in os.path.basename(p) else "Sans", []).append(p)
    out = {}
    for fam, ps in fams.items():
        asc = desc = 0
        for p in ps:
            f = TTFont(p)
            g = f["glyf"]
            for n in f.getGlyphOrder():
                if g[n].numberOfContours:
                    g[n].recalcBounds(g)
                    asc = max(asc, g[n].yMax)
                    desc = max(desc, -g[n].yMin)
            f.close()
        for p in ps:
            f = TTFont(p)
            o = f["OS/2"]
            o.usWinAscent, o.usWinDescent = asc, desc
            gl, cm = f["glyf"], f.getBestCmap()
            o.sxHeight = gl[cm[ord("x")]].yMax
            o.sCapHeight = gl[cm[ord("H")]].yMax
            f.save(p)
        out[fam] = (asc, desc)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    srcs = sorted(glob.glob(os.path.join(a.src, "*.ttf")))
    if a.only:
        srcs = [s for s in srcs if a.only in os.path.basename(s)]
    jobs = [(s, os.path.join(a.out, os.path.basename(s))) for s in srcs]
    with Pool(min(len(jobs), 10)) as pool:
        res = dict(pool.map(build_one, jobs))
    win = unify_win_metrics([d for _, d in jobs])
    log = dict(fonts=res, win_metrics=win)
    with open(os.path.join(a.out, "build-log.json"), "w", encoding="utf-8") as fh:
        json.dump(log, fh, indent=1, ensure_ascii=False)
    for k, v in res.items():
        print(k, v["e"], "reduced", len(v["reduced"]), v["seconds"], "s")
    print("win", win)


if __name__ == "__main__":
    main()
