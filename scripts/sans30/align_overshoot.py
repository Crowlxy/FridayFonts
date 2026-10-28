#!/usr/bin/env python3
"""Move the round bottoms of Latin and digit glyphs with the flat feet (issue #22).

    python scripts/sans30/align_overshoot.py --src <3.002 ttf dir> --out <new ttf dir>

3.002 draws every weight with its flat feet floating around the baseline (Light +18 ...
Bold -32 at upem 2000) and the round bottoms a constant 20-24 units below the flat feet.
align_baseline.py pins the flat feet to 0 and leaves the round letters, so the overshoot
below the baseline drifts from -2 (Light) to -56 (Bold).  This moves the round bottoms by the
same amount as the feet, which restores the 3.002 relation: about -20 to -24 in every weight.

The shift fades out with height, so the bowl is bent rather than cut, a counter keeps its
stroke width, and a horizontal edge stays horizontal.  Flat feet (already on the baseline)
are held fixed.  Tops are not touched.
"""
import argparse
from pathlib import Path

from fontTools.ttLib import TTFont

import align_baseline
import fix_circled_symbols

BOTTOM_ZONE = (-100, 12)   # a round bottom is a smooth minimum with its y in this range
FULL_BELOW, NONE_ABOVE = 200, 600   # shift is whole below 200, gone at 600
FULL_SIZE = 1050           # smaller glyphs (subs, dnom: below 900) are not letters sitting on the baseline
MARK_GAP = (-140, -80)     # a mark hanging below the bowl (cedilla, ogonek) fades out here


def weight(y):
    if y >= NONE_ABOVE:
        return 0.0
    if y <= MARK_GAP[0]:
        return 0.0
    if y <= MARK_GAP[1]:
        return (y - MARK_GAP[0]) / (MARK_GAP[1] - MARK_GAP[0])
    if y <= FULL_BELOW:
        return 1.0
    t = (y - FULL_BELOW) / (NONE_ABOVE - FULL_BELOW)
    return 1 - t * t * (3 - 2 * t)


def has_round_bottom(g):
    """True if a full-size glyph has a contour with a smooth bottom (horizontal tangent) in BOTTOM_ZONE."""
    if g.numberOfContours <= 0 or g.yMax < FULL_SIZE:
        return False
    start = 0
    for end in g.endPtsOfContours:
        n = end - start + 1
        pts = [(g.coordinates[start + k][1], g.flags[start + k] & 1) for k in range(n)]
        for k in range(n):
            y, on = pts[k]
            if not BOTTOM_ZONE[0] <= y <= BOTTOM_ZONE[1]:
                continue
            (ya, ona), (yb, onb) = pts[k - 1], pts[(k + 1) % n]
            if on:
                # on-curve minimum between two level handles
                if not ona and not onb and ya == y == yb:
                    return True
            elif not onb and yb == y and ya > y and pts[(k + 2) % n][0] > y:
                # two level handles with the on-curve minimum implied between them
                return True
        start = end + 1
    return False


def fix(font, shift):
    """Shift the round bottoms by `shift` units; return the names of the glyphs changed."""
    if shift == 0:
        return set()
    glyf = font['glyf']
    limit = round(font['head'].unitsPerEm * 0.04)
    # a circled letter (ss05) is a symbol, not a letter on the baseline: leave its ring alone
    names = align_baseline.latin_glyphs(font, has_round_bottom) - set(fix_circled_symbols.targets(font))
    for name in names:
        g = glyf[name]
        pinned = align_baseline.foot_points(g, 0, limit)
        for i, (x, y) in enumerate(g.coordinates):
            if i not in pinned:
                g.coordinates[i] = (x, y + round(shift * weight(y)))
        g.recalcBounds(glyf)
    return names


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--src', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.src.resolve() == args.out.resolve():
        parser.error('source and output directories must differ')
    args.out.mkdir(parents=True, exist_ok=True)
    for path in sorted(args.src.glob('FridaySans*.ttf')):
        out = args.out / path.name
        if out.exists():
            raise FileExistsError(out)
        font = TTFont(path)
        glyf = font['glyf']
        shift = -glyf[font.getBestCmap()[ord('H')]].yMin
        names = align_baseline.align(font)
        moved = fix(font, shift)
        font.save(out)
        print(f'{path.name}: shift {shift}, {len(moved)} glyphs')


if __name__ == '__main__':
    main()
