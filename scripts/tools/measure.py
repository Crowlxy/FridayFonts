#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reproduce every number in DESIGN.md.

Outlines are never copied anywhere; this only reads geometry.

    python tools/measure.py latin      # SF Mono / Fragment / Geist
    python tools/measure.py ladder     # weight ladders + Geist wght solutions
    python tools/measure.py glyphs     # per-glyph sidebearings
    python tools/measure.py jp         # Hiragino W0-W9 (+ Zen Kaku if present)
    python tools/measure.py all

Windows: run with PYTHONUTF8=1 so the CJK output does not hit cp932.
"""
import glob
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

from scanline import get, spans, spans_v

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
SRC = os.path.join(ROOT, "Source")

SFMONO = os.path.join(SRC, "SFMonoFonts", "SF Mono Fonts")
FRAGMENT = os.path.join(SRC, "Fragment_Mono")
GEIST = os.path.join(SRC, "Geist_Mono")
ZENKAKU = os.path.join(SRC, "ZenKakuGothicNew")


def _open(path, index=-1, wght=None):
    f = TTFont(path, fontNumber=index, lazy=False)
    if wght is not None and "fvar" in f:
        f = instantiateVariableFont(f, {"wght": wght}, inplace=True, updateFontNames=False)
    return f


def scale(f):
    return 1000.0 / f["head"].unitsPerEm


def vstem(f, ch="H", fractions=(0.15, 0.22, 0.30, 0.70, 0.78, 0.85)):
    """Median vertical-stem width, scanning horizontally away from crossbars."""
    p = get(f, ch)
    if not p:
        return None
    ys = [y for poly in p for _, y in poly]
    lo, hi = min(ys), max(ys)
    widths = []
    for r in fractions:
        for a, b in spans(p, lo + (hi - lo) * r):
            widths.append((b - a) * scale(f))
    widths = [w for w in widths if w < 250]
    return statistics.median(widths) if widths else None


def hbar(f, ch="H"):
    """Thickest horizontal run down the middle of the glyph -- the crossbar."""
    p = get(f, ch)
    if not p:
        return None
    xs = [x for poly in p for x, _ in poly]
    v = spans_v(p, (min(xs) + max(xs)) / 2)
    return max(b - a for a, b in v) * scale(f) if v else None


def counter(f, ch="o"):
    """Inner width of a two-contour round glyph at half x-height."""
    p = get(f, ch)
    if not p:
        return None
    sp = spans(p, 0.5 * f["OS/2"].sxHeight)
    return (sp[1][0] - sp[0][1]) * scale(f) if len(sp) == 2 else None


def advance(f, ch="H"):
    n = f.getBestCmap().get(ord(ch))
    return f["hmtx"][n][0] * scale(f) if n else None


# --------------------------------------------------------------------------

LATIN = [
    (os.path.join(SFMONO, "SF-Mono-Regular.otf"), "SF Mono Regular (ref)", None),
    (os.path.join(FRAGMENT, "FragmentMono-Regular.ttf"), "Fragment Mono Regular", None),
    (os.path.join(GEIST, "static", "GeistMono-Regular.ttf"), "Geist Mono Regular", None),
]


def latin():
    print("=== 2.1 Latin basic dimensions (per 1000 upem) ===")
    hdr = "%-24s %6s %6s %6s %6s %6s %6s %8s"
    print(hdr % ("", "adv", "cap", "x-ht", "stem", "bar", "bar/st", "counter"))
    for path, label, wght in LATIN:
        if not os.path.exists(path):
            print("%-24s -- missing --" % label)
            continue
        f = _open(path, wght=wght)
        S = scale(f)
        st, ba = vstem(f), hbar(f)
        print(hdr % (label, "%.1f" % advance(f), "%.1f" % (f["OS/2"].sCapHeight * S),
                     "%.1f" % (f["OS/2"].sxHeight * S), "%.1f" % st, "%.1f" % ba,
                     "%.3f" % (ba / st), "%.1f" % counter(f)))
        f.close()
    print()


SF_LADDER = ["Light", "Regular", "Medium", "Semibold", "Bold", "Heavy"]


def ladder():
    print("=== 2.2 Weight ladders ===")
    targets = {}
    print("-- SF Mono (reference only) --")
    for w in SF_LADDER:
        path = os.path.join(SFMONO, "SF-Mono-%s.otf" % w)
        if not os.path.exists(path):
            continue
        f = _open(path)
        S = scale(f)
        st, ba = vstem(f), hbar(f)
        sc = st / (f["OS/2"].sCapHeight * S)
        targets[w] = sc
        print("  %-9s stem=%6.1f bar=%6.1f bar/stem=%.3f stem/cap=%.4f stem/adv=%.4f"
              % (w, st, ba, ba / st, sc, st / advance(f)))
        f.close()

    print("-- Geist Mono VF --")
    geist = {}
    for wg in range(200, 901, 100):
        f = _open(os.path.join(GEIST, "GeistMono-VariableFont_wght.ttf"), wght=wg)
        S = scale(f)
        st, ba = vstem(f), hbar(f)
        sc = st / (f["OS/2"].sCapHeight * S)
        geist[wg] = sc
        print("  wght %3d  stem=%6.1f bar=%6.1f bar/stem=%.3f stem/cap=%.4f" % (wg, st, ba, ba / st, sc))
        f.close()

    print("-- Geist wght solving SF Mono stem/cap --")
    keys = sorted(geist)
    for w in SF_LADDER:
        if w not in targets:
            continue
        t = targets[w]
        sol = None
        for a, b in zip(keys, keys[1:]):
            if geist[a] <= t <= geist[b]:
                sol = a + (t - geist[a]) / (geist[b] - geist[a]) * (b - a)
                break
        if sol is None:  # extrapolate off the top
            a, b = keys[-2], keys[-1]
            sol = b + (t - geist[b]) / (geist[b] - geist[a]) * (b - a)
        print("  %-9s target stem/cap=%.4f  ->  Geist wght %6.1f%s"
              % (w, t, sol, "  (extrapolated)" if not keys[0] <= sol <= keys[-1] else ""))
    print()


GLYPHS = "agIl1i0jrtfy"


def glyphs():
    print("=== 2.3 Per-glyph sidebearings (LSB / RSB / ink width / top / bottom) ===")
    data = {}
    for path, label, wght in LATIN:
        if not os.path.exists(path):
            continue
        f = _open(path, wght=wght)
        S = scale(f)
        cmap, hmtx = f.getBestCmap(), f["hmtx"]
        d = {}
        for ch in GLYPHS:
            n = cmap.get(ord(ch))
            if not n:
                continue
            p = get(f, ch)
            if not p:
                continue
            xs = [x for poly in p for x, _ in poly]
            ys = [y for poly in p for _, y in poly]
            d[ch] = (min(xs) * S, (hmtx[n][0] - max(xs)) * S,
                     (max(xs) - min(xs)) * S, max(ys) * S, min(ys) * S)
        data[label] = d
        f.close()
    labels = list(data)
    print("%-3s | %s" % ("ch", " | ".join("%-27s" % l for l in labels)))
    for ch in GLYPHS:
        cells = []
        for l in labels:
            d = data[l].get(ch)
            cells.append("%5.0f %5.0f %5.0f %5.0f %5.0f" % d if d else "%-27s" % "  --")
        print("%-3s | %s" % (ch, " | ".join(cells)))
    print()


JP_CHARS = "日国あア永"


def jp():
    print("=== 4.1 CJK stems and ink sizes (per 1000 upem) ===")
    paths = sorted(glob.glob(os.path.join(SRC, "*.ttc")))
    paths += sorted(glob.glob(os.path.join(ZENKAKU, "*.ttf")))
    if not any(ZENKAKU in p for p in paths):
        print("  (Zen Kaku Gothic New not found at %s)" % ZENKAKU)
    for path in paths:
        try:
            f = _open(path, index=0 if path.endswith(".ttc") else -1)
        except Exception as e:
            print("  %s  ERROR %s" % (os.path.basename(path), e))
            continue
        S = scale(f)
        cmap, hmtx = f.getBestCmap(), f["hmtx"]
        print("-- %s" % (f["name"].getDebugName(4) or os.path.basename(path)))
        for ch in JP_CHARS:
            if ord(ch) not in cmap:
                continue
            p = get(f, ch)
            xs = [x for poly in p for x, _ in poly]
            ys = [y for poly in p for _, y in poly]
            lo, hi = min(ys), max(ys)
            xlo, xhi = min(xs), max(xs)
            v = [w for r in (0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.85)
                 for a, b in spans(p, lo + (hi - lo) * r) for w in [(b - a) * S] if w < 250]
            h = [w for r in (0.15, 0.3, 0.5, 0.7, 0.85)
                 for a, b in spans_v(p, xlo + (xhi - xlo) * r) for w in [(b - a) * S] if w < 250]
            mv = statistics.median(v) if v else 0
            mh = statistics.median(h) if h else 0
            print("   %s adv=%4.0f ink %4.0f x %4.0f  y %5.0f..%4.0f  vert=%6.1f horiz=%6.1f  h/v=%.3f"
                  % (ch, hmtx[cmap[ord(ch)]][0] * S, xhi - xlo and (xhi - xlo) * S,
                     (hi - lo) * S, lo * S, hi * S, mv, mh, (mh / mv) if mv else 0))
        f.close()
    print()


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name, fn in (("latin", latin), ("ladder", ladder), ("glyphs", glyphs), ("jp", jp)):
        if what in (name, "all"):
            fn()


if __name__ == "__main__":
    main()
