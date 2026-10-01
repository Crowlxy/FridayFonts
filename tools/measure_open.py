#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Measure the questions DESIGN.md section 7 left open.

    python tools/measure_open.py widths     # 7.1  lowercase ink width and sidebearings
    python tools/measure_open.py counters   # 7.2  the counter of `o` across the weights
    python tools/measure_open.py corners    # 7.3  terminal rounding radius
    python tools/measure_open.py strokes    # 7.4  harai / tome / hane, Hiragino vs Zen Kaku
    python tools/measure_open.py all

Outlines are read, never copied.  Run with PYTHONUTF8=1 on Windows.
"""
import math
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

from scanline import flatten, spans, spans_v
from fontTools.pens.recordingPen import DecomposingRecordingPen

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SRC = os.path.join(ROOT, "Source")
SFMONO = os.path.join(SRC, "SFMonoFonts", "SF Mono Fonts")
GEIST = os.path.join(SRC, "Geist_Mono", "GeistMono-VariableFont_wght.ttf")
ZENKAKU = os.path.join(SRC, "ZenKakuGothicNew", "ZenKakuGothicNew-%s.ttf")
# The Hiragino filenames came off a Mac and are stored decomposed (NFD), so a
# composed literal never matches.  Resolve them by pattern instead.
import glob as _glob
import unicodedata as _ud


def _hiragino(w):
    want = _ud.normalize("NFC", "ヒラギノ角ゴシック W%d.ttc" % w)
    for p in _glob.glob(os.path.join(SRC, "*.ttc")):
        if _ud.normalize("NFC", os.path.basename(p)) == want:
            return p
    return os.path.join(SRC, want)
BUILT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts",
                     "InoriMono-%s.ttf")


def _open(path, index=-1, wght=None):
    f = TTFont(path, fontNumber=index, lazy=False)
    if wght is not None and "fvar" in f:
        f = instantiateVariableFont(f, {"wght": wght}, inplace=True,
                                    updateFontNames=False)
    return f


def upm(f):
    return 1000.0 / f["head"].unitsPerEm


def polys(f, ch):
    """Flattened contours of one character, composites decomposed."""
    name = f.getBestCmap().get(ord(ch))
    if not name:
        return None
    gs = f.getGlyphSet()
    pen = DecomposingRecordingPen(gs)
    gs[name].draw(pen)
    p = flatten(pen.value)
    return p or None


def advance(f, ch):
    name = f.getBestCmap().get(ord(ch))
    return f["hmtx"][name][0] * upm(f) if name else None


def ink(f, ch):
    """(xmin, ymin, xmax, ymax) in 1000-upem units."""
    p = polys(f, ch)
    if not p:
        return None
    s = upm(f)
    xs = [x for c in p for x, _ in c]
    ys = [y for c in p for _, y in c]
    return min(xs) * s, min(ys) * s, max(xs) * s, max(ys) * s


def vstem(f, ch="H", cuts=(0.15, 0.22, 0.30, 0.70, 0.78, 0.85)):
    p = polys(f, ch)
    if not p:
        return None
    ys = [y for c in p for _, y in c]
    lo, hi = min(ys), max(ys)
    w = [(b - a) * upm(f) for r in cuts for a, b in spans(p, lo + (hi - lo) * r)]
    w = [x for x in w if x < 250]
    return statistics.median(w) if w else None


# ---------------------------------------------------------------------------
# 7.1  How wide is the lowercase, and where does it sit in the cell?


LOWER = "aeonumsrcgbdpqxz"


def widths():
    print("=== 7.1  lowercase ink width and sidebearings ===")
    print("Ink width as a fraction of the advance, and of the same font's `H`.")
    print("The second number is the one that carries design intent: it is free")
    print("of how wide the designer chose to make the cell.\n")

    rows = []
    rows.append(("SF Mono Regular", _open(os.path.join(SFMONO, "SF-Mono-Regular.otf"))))
    rows.append(("Geist Mono 400", _open(GEIST, wght=400)))
    if os.path.exists(BUILT % "Regular"):
        rows.append(("Inori Mono Regular", _open(BUILT % "Regular")))

    print("%-20s %6s %6s | %s" % ("", "adv", "H ink", "  ".join("%5s" % c for c in LOWER)))
    for label, f in rows:
        adv = advance(f, "H")
        hb = ink(f, "H")
        hw = hb[2] - hb[0]
        cells = []
        for c in LOWER:
            b = ink(f, c)
            cells.append("%5.3f" % ((b[2] - b[0]) / hw) if b else "    -")
        print("%-20s %6.1f %6.1f | %s" % (label, adv, hw, "  ".join(cells)))

    print("\nsame, as a fraction of the advance:")
    for label, f in rows:
        adv = advance(f, "H")
        cells = []
        for c in LOWER:
            b = ink(f, c)
            cells.append("%5.3f" % ((b[2] - b[0]) / adv) if b else "    -")
        print("%-20s %6.1f %6s | %s" % (label, adv, "", "  ".join(cells)))

    print("\nsidebearings of the stem-ending letters (left, right, in units):")
    for label, f in rows:
        adv = advance(f, "H")
        out = []
        for c in "nume":
            b = ink(f, c)
            if b:
                out.append("%s L%5.1f R%5.1f" % (c, b[0], adv - b[2]))
        print("%-20s %s" % (label, "   ".join(out)))


# ---------------------------------------------------------------------------
# 7.2  The counter of `o`


def counter_of(f, ch="o"):
    """Width of the widest hole, and the ink width, at the vertical middle."""
    p = polys(f, ch)
    if not p:
        return None
    s = upm(f)
    ys = [y for c in p for _, y in c]
    y = (min(ys) + max(ys)) / 2
    runs = spans(p, y)
    if len(runs) < 2:
        return None
    ink_w = (runs[-1][1] - runs[0][0]) * s
    holes = [(runs[i + 1][0] - runs[i][1]) * s for i in range(len(runs) - 1)]
    return max(holes), ink_w


SF_FILES = [("Light", "SF-Mono-Light.otf"), ("Regular", "SF-Mono-Regular.otf"),
            ("Medium", "SF-Mono-Medium.otf"), ("Bold", "SF-Mono-Bold.otf"),
            ("Black", "SF-Mono-Heavy.otf")]


def counters():
    print("=== 7.2  the counter of `o` across the weights ===")
    print("counter / ink width.  A face that only thickens its stems loses")
    print("counter faster than SF Mono does; SF widens the letter to hold it.\n")
    print("%-9s | %-22s | %-22s" % ("", "SF Mono", "Inori Mono"))
    print("%-9s | %6s %6s %6s | %6s %6s %6s"
          % ("weight", "count", "ink", "ratio", "count", "ink", "ratio"))
    for style, fn in SF_FILES:
        sf = _open(os.path.join(SFMONO, fn))
        c = counter_of(sf)
        line = "%-9s | %6.1f %6.1f %6.3f" % (style, c[0], c[1], c[0] / c[1])
        if os.path.exists(BUILT % style):
            ic = counter_of(_open(BUILT % style))
            line += " | %6.1f %6.1f %6.3f" % (ic[0], ic[1], ic[0] / ic[1])
        print(line)


# ---------------------------------------------------------------------------
# 7.3  Terminal rounding


def corner_radius(f, ch, corner="tl", char_for_box=None):
    """Fillet radius at one bounding-box corner of a glyph.

    A sharp corner puts a point of the outline exactly on the corner of the
    bounding box.  A circular fillet of radius r pulls the outline back along
    the diagonal by r*(sqrt(2)-1), so the shortest distance from the box corner
    to the outline gives r directly.  Only meaningful on a corner that really
    is a stem end -- `H` top-left, `I` and `l` in most faces.
    """
    p = polys(f, ch)
    if not p:
        return None
    s = upm(f)
    xs = [x for c in p for x, _ in c]
    ys = [y for c in p for _, y in c]
    cx = min(xs) if corner[1] == "l" else max(xs)
    cy = max(ys) if corner[0] == "t" else min(ys)
    d = min(math.hypot(x - cx, y - cy) for c in p for x, y in c)
    return d * s / (math.sqrt(2) - 1)


def corners():
    print("=== 7.3  terminal rounding radius ===")
    print("Shortest distance from the bounding-box corner to the outline,")
    print("read as a circular fillet.  Values under ~1.5 are the flattening")
    print("error of the polygoniser, not a rounding.\n")
    print("%-22s %8s %8s %8s %8s" % ("", "H tl", "H tr", "H bl", "I tl"))
    rows = [("SF Mono Light", os.path.join(SFMONO, "SF-Mono-Light.otf"), None),
            ("SF Mono Regular", os.path.join(SFMONO, "SF-Mono-Regular.otf"), None),
            ("SF Mono Bold", os.path.join(SFMONO, "SF-Mono-Bold.otf"), None),
            ("SF Mono Heavy", os.path.join(SFMONO, "SF-Mono-Heavy.otf"), None),
            ("Geist Mono 400", GEIST, 400),
            ("Geist Mono 900", GEIST, 900)]
    if os.path.exists(BUILT % "Regular"):
        rows.append(("Inori Mono Regular", BUILT % "Regular", None))
    for label, path, w in rows:
        f = _open(path, wght=w)
        vals = [corner_radius(f, "H", "tl"), corner_radius(f, "H", "tr"),
                corner_radius(f, "H", "bl"), corner_radius(f, "I", "tl")]
        print("%-22s %s" % (label, " ".join("%8.2f" % v if v else "       -"
                                            for v in vals)))

    print("\nSame probe on the CJK sources (a kanji terminal, `国` top-left):")
    for label, path, idx in [("Hiragino W3", _hiragino(3), 0),
                             ("Zen Kaku Regular", ZENKAKU % "Regular", -1)]:
        if not os.path.exists(path):
            continue
        f = _open(path, index=idx)
        print("%-22s %8.2f" % (label, corner_radius(f, "国", "tl")))


# ---------------------------------------------------------------------------
# 7.4  harai / tome / hane


def width_profile(f, ch, n=9, axis="h"):
    """Stroke width at n points down (or across) the glyph, in 1000-upem units."""
    p = polys(f, ch)
    if not p:
        return None
    s = upm(f)
    if axis == "h":
        vals = [y for c in p for _, y in c]
        cut = spans
    else:
        vals = [x for c in p for x, _ in c]
        cut = spans_v
    lo, hi = min(vals), max(vals)
    out = []
    for i in range(n):
        t = lo + (hi - lo) * (i + 0.5) / n
        runs = cut(p, t)
        out.append(max((b - a) * s for a, b in runs) if runs else 0.0)
    return out


def strokes():
    print("=== 7.4  harai / tome / hane ===")
    print("Every width is divided by the face's own kanji stem so the")
    print("comparison is of shape, not of weight.\n")

    faces = []
    for w in (3, 4, 6):
        path = _hiragino(w)
        if os.path.exists(path):
            faces.append(("Hiragino W%d" % w, _open(path, index=0)))
    for s in ("Light", "Regular", "Medium", "Bold"):
        faces.append(("Zen Kaku %s" % s, _open(ZENKAKU % s)))
    if os.path.exists(BUILT % "Regular"):
        faces.append(("Inori Mono Regular", _open(BUILT % "Regular")))

    def stem(f):
        vals = []
        for ch in "日国目田":
            p = polys(f, ch)
            if not p:
                continue
            ys = [y for c in p for _, y in c]
            lo, hi = min(ys), max(ys)
            for r in (0.3, 0.5, 0.7):
                vals += [(b - a) * upm(f) for a, b in spans(p, lo + (hi - lo) * r)]
        vals = [v for v in vals if 10 < v < 200]
        return statistics.median(vals) if vals else None

    print("harai -- width down the sweep of ノ (katakana no), tip last:")
    for label, f in faces:
        st = stem(f)
        pr = width_profile(f, "ノ")
        if pr and st:
            print("  %-20s %s   tip/base %.2f"
                  % (label, " ".join("%5.2f" % (v / st) for v in pr),
                     pr[-1] / pr[0] if pr[0] else 0))

    print("\ntome -- width up the vertical of 十 (ten), bottom first:")
    for label, f in faces:
        st = stem(f)
        p = polys(f, "十")
        if not p or not st:
            continue
        s = upm(f)
        ys = [y for c in p for _, y in c]
        lo, hi = min(ys), max(ys)
        out = []
        for r in (0.02, 0.06, 0.12, 0.25, 0.5):
            runs = spans(p, lo + (hi - lo) * r)
            runs = [(a, b) for a, b in runs if (b - a) * s < 200]
            out.append(max((b - a) * s for a, b in runs) / st if runs else 0.0)
        print("  %-20s %s" % (label, " ".join("%5.3f" % v for v in out)))

    print("\nhane -- the hook of 亅 (hanebo): hook reach / stem, and its depth:")
    for label, f in faces:
        st = stem(f)
        p = polys(f, "亅")
        if not p or not st:
            continue
        s = upm(f)
        xs = [x for c in p for x, _ in c]
        ys = [y for c in p for _, y in c]
        # the hook is the ink left of the stem, at the bottom of the glyph
        stem_x = max(xs)
        reach = (stem_x - min(xs)) * s
        depth = 0.0
        for i in range(12):
            y = min(ys) + (max(ys) - min(ys)) * i / 40.0
            runs = spans(p, y)
            if runs:
                depth = max(depth, (runs[-1][1] - runs[0][0]) * s)
        print("  %-20s reach %6.1f (%.2f stems)  bottom span %6.1f (%.2f)"
              % (label, reach, reach / st, depth, depth / st))

    print("\nkana skeleton -- ink box of あ and ア over the kanji ink:")
    for label, f in faces:
        kb = ink(f, "国")
        for ch in ("あ", "ア"):
            b = ink(f, ch)
            if b and kb:
                print("  %-20s %s  w %.3f  h %.3f"
                      % (label, ch, (b[2] - b[0]) / (kb[2] - kb[0]),
                         (b[3] - b[1]) / (kb[3] - kb[1])))


def main():
    cmds = {"widths": widths, "counters": counters, "corners": corners,
            "strokes": strokes}
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name, fn in cmds.items():
        if which in ("all", name):
            fn()
            print()


if __name__ == "__main__":
    main()
