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
import repair_light as RL  # noqa: E402
import fixups as FX  # noqa: E402

VERSION = "3.002"
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
    # Two contours that touch within a unit or so (a hairline gap in the 2.5 outline) fuse under
    # any offset.  The topology after half a unit is accepted as well as the original one, so
    # that such a glyph is widened too instead of staying at its 2.5 outline.
    n1 = n0
    try:
        n1 = min(n0, len(list(quantized(offset_path(base, 0.5)).contours)))     # fusion only, never a new piece
    except pathops.PathOpsError:
        pass

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
        return out, len(list(q.contours)) in (n0, n1) and abs(grown - x) <= max(0.15 * x, 0.5)

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


WEIGHTS = ["Light", "Regular", "Medium", "SemiBold", "Bold"]


def prepared_face(path, ui):
    """A 2.5 face as 3.0 starts from it: working em, Light kanji repaired."""
    f = TTFont(path)
    to_working_em(f, ui)
    if weight_of(os.path.basename(path)[:-4]) == "Light":
        reg = TTFont(path.replace("-Light", "-Regular"))
        to_working_em(reg, ui)
        RL.repair(f, reg, tt_glyph)
    return f


LADDER_KEEP = 0.5        # a glyph keeps at least this fraction of 2.5's weight-to-weight area step


def _areas(f):
    from fontTools.pens.areaPen import AreaPen
    gs, out = f.getGlyphSet(), {}
    for n in f.getGlyphOrder():
        if f["glyf"][n].numberOfContours > 0 and n.startswith("jp."):
            pen = AreaPen(gs)
            gs[n].draw(pen)
            out[n] = abs(pen.value)
    return out


def ladder_pass(res, srcs, outdir):
    """Keep the weight-to-weight step of a kanji from collapsing.

    widen() bisects the offset of a dense kanji down until its gaps stay open; the heavier the
    weight, the less room there is, so SemiBold could end up widened much less than Medium (it
    was thinner than Medium in 14 glyphs, and under half of 2.5's step in about 240).  From the
    heaviest weight down, a glyph whose area step to the next heavier weight is under
    LADDER_KEEP of the 2.5 step is rebuilt with a smaller offset (the heavier face cannot take
    more).  Returns {face: {glyph: (offset before, offset after)}}.
    """
    changed = {}
    by_family = {}
    for src in srcs:
        base = os.path.basename(src)[:-4]
        by_family.setdefault("UI" if "SansUI" in base else "Sans", {})[weight_of(base)] = (base, src)
    for fam, faces in by_family.items():
        ui = fam == "UI"
        a25 = {w: _areas(prepared_face(src, ui)) for w, (base, src) in faces.items()}
        outs = {w: TTFont(os.path.join(outdir, base + ".ttf")) for w, (base, src) in faces.items()}
        a30 = {w: _areas(f) for w, f in outs.items()}
        for w_hi, w_lo in zip(WEIGHTS[::-1], WEIGHTS[::-1][1:]):
            if w_hi not in faces or w_lo not in faces:
                continue
            base, src = faces[w_lo]
            full = K_EMBOLDEN * STEM[w_lo] * 2.0
            cur = res[base]["used"]
            face = None
            for n, a_lo in list(a30[w_lo].items()):
                if n not in a30[w_hi] or n not in a25[w_lo] or n not in a25[w_hi]:
                    continue
                s25 = a25[w_hi][n] / a25[w_lo][n] - 1
                if s25 < 0.01:
                    continue
                target = a30[w_hi][n] / (1 + (LADDER_KEEP + 0.05) * s25)   # aim a little above the floor the check uses
                if a_lo <= a30[w_hi][n] / (1 + LADDER_KEEP * s25):
                    continue
                if face is None:
                    face = prepared_face(src, ui)
                    gs, out = face.getGlyphSet(), outs[w_lo]
                    glyf, hmtx, vmtx = out["glyf"], out["hmtx"], out["vmtx"]
                    dv, dc = K_CONVEX * STEM[w_lo] * 2.0, K_CONCAVE * STEM[w_lo] * 2.0
                    log = changed.setdefault(base, {})
                g_old = glyf[n]
                vorg = vmtx[n][1] + g_old.yMax
                cons = S.contours_from(gs, n)
                soft = [S.soften_contour(c, dv, dc) for c in cons]
                if count(soft) != count(cons):
                    soft = cons
                before = cur.get(n, full)
                e_try, area, got = before, a_lo, before
                for _ in range(3):
                    p = pathops.Path()
                    glyf[n].draw(p.getPen(glyphSet=None), glyf)
                    per = perimeter(p) or 1.0
                    e_try = max(0.0, e_try + (target - area) / per)
                    glyf[n], got = widen(soft, e_try)
                    glyf[n].recalcBounds(glyf)
                    from fontTools.pens.areaPen import AreaPen
                    pen = AreaPen(None)
                    glyf[n].draw(pen, glyf)
                    area = abs(pen.value)
                    if area <= target * 1.001 or e_try <= 0:
                        break
                g = glyf[n]
                hmtx[n] = (hmtx[n][0], g.xMin)
                vmtx[n] = (vmtx[n][0], vorg - g.yMax)
                a30[w_lo][n] = area
                cur[n] = round(got, 4)
                log[n] = (round(before, 3), round(got, 3))
            if face is not None:
                outs[w_lo].save(os.path.join(outdir, base + ".ttf"))
    return changed


def finish(jobs):
    """Last step on the saved faces: GDEF mark class for zero-width combining glyphs."""
    out = {}
    for _, dst in jobs:
        f = TTFont(dst)
        done = FX.classify_zero_width_marks(f)
        if done:
            f.save(dst)
        out[os.path.basename(dst)[:-4]] = len(done)
    return out


def build_one(args):
    src, dst = args
    base = os.path.basename(src)[:-4]
    weight = weight_of(base)
    f = TTFont(src)
    to_working_em(f, "SansUI" in base)
    approx = FX.add_approx_equal(f)
    zero_marks = {}
    if weight != "Light":
        light = TTFont(src.replace("-" + weight, "-Light"))
        zero_marks = FX.zero_width_like_light(f, light)
    scale = f["head"].unitsPerEm / 1000.0
    stem = STEM[weight] * scale
    dv, dc, e = K_CONVEX * stem, K_CONCAVE * stem, K_EMBOLDEN * stem
    gs, glyf = f.getGlyphSet(), f["glyf"]
    old = {}
    for n in f.getGlyphOrder():
        g = glyf[n]
        old[n] = g.yMax if g.numberOfContours != 0 else None
    vorg = {n: f["vmtx"][n][1] + old[n] for n in old if old[n] is not None}
    repaired = {}
    if weight == "Light":
        # 2.5 Light has kanji with a wedge, a spur or a missing stroke: rebuild them from Regular
        reg = TTFont(src.replace("-Light", "-Regular"))
        to_working_em(reg, "SansUI" in base)
        repaired = RL.repair(f, reg, tt_glyph)
        gs = f.getGlyphSet()
    script_g = 0
    if weight == "Bold":
        sb = TTFont(src.replace("-Bold", "-SemiBold"))
        to_working_em(sb, "SansUI" in base)
        script_g = FX.lower_bold_script_g(f, sb)
    areas, kanji_median = ink_areas(f)
    reduced = {}
    used_log = {}
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
        if used < e - 1e-6:
            used_log[n] = round(used, 4)
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
    names_added = FX.add_feature_names(f)
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
    # Fontspector (universal profile): Windows name records carry every name (no Mac records, and
    # with them no ltag, an AAT table), no trailing white space, xAvgCharWidth from the glyphs.
    name.names = [r for r in name.names if r.platformID != 1]
    for r in name.names:
        text = r.toUnicode()
        if text != text.strip():
            r.string = text.strip()
    if "ltag" in f:
        del f["ltag"]
    f["OS/2"].recalcAvgCharWidth(f)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    f.save(dst)
    return base, dict(dv=round(dv, 2), dc=round(dc, 2), e=round(e, 2), reduced=reduced, used=used_log, lighter=len(lighter), kept_sharp=kept_sharp, failed=failed, repaired=repaired,
                      approx_equal=approx, feature_names=len(names_added), script_g_shift=script_g, zero_width_marks=len(zero_marks),
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
    ap.add_argument("--no-ladder", action="store_true", help="skip the weight-step pass (saves build-log.json first)")
    ap.add_argument("--finish-only", action="store_true", help="only the last step (GDEF mark classes) on an existing --out")
    ap.add_argument("--ladder-only", action="store_true", help="run only the weight-step pass on an existing --out built with --no-ladder")
    a = ap.parse_args()
    srcs = sorted(glob.glob(os.path.join(a.src, "*.ttf")))
    if a.only:
        srcs = [s for s in srcs if a.only in os.path.basename(s)]
    jobs = [(s, os.path.join(a.out, os.path.basename(s))) for s in srcs]
    logpath = os.path.join(a.out, "build-log.json")
    if a.ladder_only or a.finish_only:
        with open(logpath, encoding="utf-8") as fh:
            res = json.load(fh)["fonts"]
    else:
        with Pool(min(len(jobs), 10)) as pool:
            res = dict(pool.map(build_one, jobs))
        with open(logpath, "w", encoding="utf-8") as fh:
            json.dump(dict(fonts=res), fh, indent=1, ensure_ascii=False)
    if a.finish_only:
        with open(logpath, encoding="utf-8") as fh:
            ladder = json.load(fh).get("ladder", {})        # keep the record of the earlier pass
    else:
        ladder = {} if (a.only or a.no_ladder) else ladder_pass(res, srcs, a.out)
    marks = finish(jobs)
    win = unify_win_metrics([d for _, d in jobs])
    log = dict(fonts=res, win_metrics=win, ladder=ladder, gdef_marks_added=marks)
    with open(logpath, "w", encoding="utf-8") as fh:
        json.dump(log, fh, indent=1, ensure_ascii=False)
    for k, v in res.items():
        print(k, v["e"], "reduced", len(v["reduced"]), v["seconds"], "s")
    print("ladder: rebuilt", {k: len(v) for k, v in ladder.items()})
    print("win", win)


if __name__ == "__main__":
    main()
