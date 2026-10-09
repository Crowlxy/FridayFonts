#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify the 3.0 faces against the 2.5 faces they were made from.

    python verify_sans_30.py --src <2.5 ttf dir> --out <3.0 ttf dir> [--report report.json]

Per glyph: contour count, ink growth against a clean offset, bounding box, outline
direction, advance.  Per face: tables, metrics, glyph set, GSUB/GPOS lookups.

There is no local-excess (tile) guard.  Where a narrow gap closes in only one place the
whole-glyph growth ratio can miss it; the build bisects the offset on topology and growth,
and the dense kanji (談 薬 鶏 遮 坐 鬱) are checked by eye in reports/ instead.
"""
import argparse
import glob
import json
import os
import sys
from multiprocessing import Pool

from fontTools.ttLib import TTFont
from fontTools.pens.areaPen import AreaPen
import pathops

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_sans_30 as B  # noqa: E402


# Dense kanji whose contour count differs from 2.5 after emboldening (a narrow gap closed or
# opened).  Recorded as (2.5 count, 3.0 count) per face and checked by eye in reports/.
# Any other change, or a different count for these glyphs, fails the run.
KNOWN_CONTOUR_CHANGES = {
    "FridaySans-Bold": {"jp.uni737C": (6, 5), "jp.uni7E6D": (8, 7), "jp.uni9F4E": (11, 12)},
    "FridaySans-Light": {"jp.glyph62569": (13, 14), "jp.uni5F8C": (5, 4), "jp.uni9B43": (7, 10)},
    "FridaySans-Medium": {"jp.glyph62646": (5, 6), "jp.uni6B53": (5, 4)},
    "FridaySans-Regular": {"jp.glyph62373": (10, 11), "jp.glyph62491": (10, 11), "jp.uni7027": (10, 11), "jp.uni81D8": (14, 15)},
    "FridaySans-SemiBold": {"jp.uni6516": (11, 12)},
    "FridaySansUI-Bold": {"jp.uni5DB8": (7, 9), "jp.uni7E6D": (8, 7)},
    "FridaySansUI-Light": {"jp.glyph62569": (13, 14), "jp.uni5F8C": (5, 4), "jp.uni9B43": (7, 10)},
    "FridaySansUI-Medium": {"jp.glyph62646": (5, 6)},
    "FridaySansUI-Regular": {"jp.glyph62373": (10, 11), "jp.glyph62491": (10, 11), "jp.uni7027": (10, 11), "jp.uni81D8": (14, 15), "jp.uni8CF8": (12, 13)},
    "FridaySansUI-SemiBold": {"jp.uni6516": (11, 12)},
}


def to_path(gs, name):
    p = pathops.Path()
    gs[name].draw(p.getPen(glyphSet=gs))
    return p


def load_src(src):
    """The 2.5 face as 3.0 reads it: Sans UI is reinterpreted as em 1010 and rescaled to 1000."""
    f = TTFont(src)
    B.to_working_em(f, "SansUI" in os.path.basename(src))
    return f


def glyph_checks(args):
    src, dst = args
    a, b = load_src(src), TTFont(dst)
    base = os.path.basename(dst)[:-4]
    weight = B.weight_of(base)
    scale = a["head"].unitsPerEm / 1000.0
    e = B.K_EMBOLDEN * B.STEM[weight] * scale
    ga, gb = a.getGlyphSet(), b.getGlyphSet()
    A, Bg = a["glyf"], b["glyf"]
    issues = {"contour_count": [], "empty": [], "growth": [], "bbox": [], "orientation": [],
              "advance": [], "composite_changed": []}
    ratios = []
    for n in a.getGlyphOrder():
        ca, cb = A[n].numberOfContours, Bg[n].numberOfContours
        if A[n].isComposite() != Bg[n].isComposite():
            issues["composite_changed"].append(n)
            continue
        if ca == 0:
            if cb != 0:
                issues["empty"].append(n)
            continue
        if cb == 0:
            issues["empty"].append(n)
            continue
        if A[n].isComposite():
            continue
        pa, pb = to_path(ga, n), to_path(gb, n)
        sa = pathops.Path(pa)
        sa.simplify(fix_winding=True)
        sb = pathops.Path(pb)
        sb.simplify(fix_winding=True)
        na, nb = len(list(sa.contours)), len(list(sb.contours))
        if na != nb:
            issues["contour_count"].append((n, na, nb))
        aa, ab = abs(sa.area), abs(sb.area)
        per = B.perimeter(sa) or 0
        if per and aa:
            growth = (ab - aa) / per
            ratios.append(growth)
            # growth/side is e at most (reduced glyphs get less, never more), and not negative
            if growth < -0.5 * scale or growth > e * 1.25 + scale:
                issues["growth"].append((n, round(growth, 2)))
        xa = (A[n].xMin, A[n].yMin, A[n].xMax, A[n].yMax)
        xb = (Bg[n].xMin, Bg[n].yMin, Bg[n].xMax, Bg[n].yMax)
        if (xb[0] < xa[0] - e - 2 * scale or xb[1] < xa[1] - e - 2 * scale
                or xb[2] > xa[2] + e + 2 * scale or xb[3] > xa[3] + e + 2 * scale):
            issues["bbox"].append((n, xa, xb))
        if xb[0] > xa[0] + 14 * scale or xb[1] > xa[1] + 14 * scale or xb[2] < xa[2] - 14 * scale or xb[3] < xa[3] - 14 * scale:
            issues["bbox"].append((n, xa, xb))       # fillets may pull an extreme in a little
        # outer contour orientation (TrueType: clockwise = negative area, y up)
        ap_ = AreaPen()
        gb[n].draw(ap_)
        if ap_.value > 0:
            issues["orientation"].append(n)
        if a["hmtx"][n][0] != b["hmtx"][n][0] and not (0x2000 <= 0 <= 0x2003):
            issues["advance"].append((n, a["hmtx"][n][0], b["hmtx"][n][0]))
    summary = {k: (len(v), v[:12]) for k, v in issues.items()}
    med = sorted(ratios)[len(ratios) // 2] if ratios else None
    return base, dict(summary=summary, median_growth=med, e=e)


def layout_digest(font, tag):
    """Content of a GSUB/GPOS table as XML text, so a changed lookup is not mistaken for an equal one."""
    from fontTools.misc.xmlWriter import XMLWriter
    import io
    buf = io.StringIO()
    w = XMLWriter(buf)
    font[tag].toXML(w, font)
    return buf.getvalue()


def glyph_failures(base, summary):
    """Glyph-level issues that are not recorded as known: each one fails the run."""
    bad = []
    known = KNOWN_CONTOUR_CHANGES.get(base, {})
    for k, (count, rows) in summary.items():
        if k == "contour_count":
            bad += [(k, row[0]) for row in rows if known.get(row[0]) != tuple(row[1:])]
            if count > len(rows):
                bad.append((k, "%d more" % (count - len(rows))))
        elif count:
            bad += [(k, "%d glyphs" % count)]
    return bad


def face_failures(f, ui):
    """Face-level checks that must hold; each name is a reason to exit non-zero."""
    bad = []
    if f["glyphs"][0] != f["glyphs"][1]:
        bad.append("glyphs")
    for k in ("cmap_equal", "order_equal", "typo_same", "hhea_same", "gsub_gpos_same", "win_covers"):
        if not f[k]:
            bad.append(k)
    if f["hinting_left"]:
        bad.append("hinting_left")
    if set(f["tables_lost"]) - {"cvt ", "fpgm", "prep"}:      # 3.0 drops the TrueType hinting on purpose
        bad.append("tables_lost")
    return bad


def face_checks(dst, src):
    a, b = load_src(src), TTFont(dst)
    out = {}
    out["glyphs"] = (a["maxp"].numGlyphs, b["maxp"].numGlyphs)
    out["cmap_equal"] = a.getBestCmap() == b.getBestCmap()
    out["order_equal"] = a.getGlyphOrder() == b.getGlyphOrder()
    out["hinting_left"] = [t for t in ("fpgm", "prep", "cvt ") if t in b]
    out["gasp"] = b["gasp"].gaspRange
    out["tables_lost"] = sorted(set(a.keys()) - set(b.keys()))
    o, oa = b["OS/2"], a["OS/2"]
    out["vend"] = o.achVendID
    out["win"] = (o.usWinAscent, o.usWinDescent)
    ui = "SansUI" in os.path.basename(dst)
    want = B.UI_LINE + (0,) if ui else None
    out["typo_same"] = ((o.sTypoAscender, o.sTypoDescender, o.sTypoLineGap) == (
        oa.sTypoAscender, oa.sTypoDescender, oa.sTypoLineGap)) if not ui else         (o.sTypoAscender, o.sTypoDescender, o.sTypoLineGap) == (want[0], want[1], 0)
    out["hhea_same"] = ((b["hhea"].ascent, b["hhea"].descent, b["hhea"].lineGap) == (
        a["hhea"].ascent, a["hhea"].descent, a["hhea"].lineGap)) if not ui else         (b["hhea"].ascent, b["hhea"].descent, b["hhea"].lineGap) == (want[0], want[1], 0)
    out["gsub_gpos_same"] = all(
        len(a[t].table.LookupList.Lookup) == len(b[t].table.LookupList.Lookup)
        and layout_digest(a, t) == layout_digest(b, t)
        for t in ("GSUB", "GPOS"))
    # win metrics must cover every glyph
    g = b["glyf"]
    ymax = max(g[n].yMax for n in b.getGlyphOrder() if g[n].numberOfContours)
    ymin = min(g[n].yMin for n in b.getGlyphOrder() if g[n].numberOfContours)
    out["win_covers"] = o.usWinAscent >= ymax and o.usWinDescent >= -ymin
    out["head_bbox"] = (b["head"].yMin, b["head"].yMax)
    out["name5"] = b["name"].getDebugName(5)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", default="")
    a = ap.parse_args()
    outs = sorted(glob.glob(os.path.join(a.out, "*.ttf")))
    jobs = [(os.path.join(a.src, os.path.basename(p)), p) for p in outs]
    with Pool(min(len(jobs), 10)) as pool:
        res = dict(pool.map(glyph_checks, jobs))
    bad = 0
    report = {}
    for src, dst in jobs:
        base = os.path.basename(dst)[:-4]
        r = res[base]
        r["face"] = face_checks(dst, src)
        report[base] = r
        s = r["summary"]
        counts = {k: v[0] for k, v in s.items() if v[0]}
        print(base, "median growth/side %.2f (e=%.2f)" % (r["median_growth"], r["e"]), counts or "glyph checks clean")
        f = r["face"]
        print("   face:", {k: f[k] for k in ("glyphs", "cmap_equal", "order_equal", "hinting_left", "gasp",
                                            "tables_lost", "vend", "win", "typo_same", "hhea_same",
                                            "gsub_gpos_same", "win_covers", "name5")})
        failed = glyph_failures(base, s)
        if failed:
            print("   GLYPH CHECK FAILED:", failed[:12])
        bad += len(failed)
        failed = face_failures(f, "SansUI" in base)
        if failed:
            print("   FACE CHECK FAILED:", failed)
            bad += len(failed)
    if a.report:
        with open(a.report, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1, ensure_ascii=False, default=str)
    if bad:
        print("FAILED: %d problem(s)" % bad)
        return 1
    print("OK: no problems")
    return 0


if __name__ == "__main__":
    sys.exit(main())
