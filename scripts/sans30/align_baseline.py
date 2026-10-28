#!/usr/bin/env python3
"""Make flat Latin and digit bottoms meet the baseline in existing Sans 3.0 TTFs.

    python scripts/sans30/align_baseline.py --src <ttf dir> --out <new ttf dir>
"""
import argparse
from pathlib import Path
import unicodedata

from fontTools.ttLib import TTFont


def foot_points(g, baseline, limit):
    if g.numberOfContours <= 0:
        return set()
    selected = set()
    start = 0
    for end in g.endPtsOfContours:
        indices = list(range(start, end + 1))
        for pos, i in enumerate(indices):
            j = indices[(pos + 1) % len(indices)]
            a, b = g.coordinates[i], g.coordinates[j]
            if not (g.flags[i] & 1 and g.flags[j] & 1 and a[1] == b[1] == baseline and a[0] != b[0]):
                continue
            selected.update((i, j))
            for origin, step in ((pos, -1), ((pos + 1) % len(indices), 1)):
                for distance in range(1, len(indices)):
                    k = indices[(origin + step * distance) % len(indices)]
                    if not baseline <= g.coordinates[k][1] <= limit:
                        break
                    selected.add(k)
                    if g.flags[k] & 1:
                        break
        start = end + 1
    return selected


def targets(font, baseline):
    glyf = font['glyf']
    limit = baseline + round(font['head'].unitsPerEm * 0.04)
    names = {name for cp, name in font.getBestCmap().items()
             if unicodedata.name(chr(cp), '').startswith(('LATIN ', 'DIGIT '))
             and foot_points(glyf[name], baseline, limit)}
    if 'GSUB' not in font or font['GSUB'].table.LookupList is None:
        return names
    # Follow substitutions so stylistic alternates and ligatures keep the same baseline.
    lookups = font['GSUB'].table.LookupList.Lookup
    while True:
        extra = set()
        for lookup in lookups:
            for sub in lookup.SubTable:
                sub = getattr(sub, 'ExtSubTable', sub)
                for src, dst in getattr(sub, 'mapping', {}).items():
                    if src in names:
                        extra.update(dst if isinstance(dst, list) else [dst])
                for src, dst in getattr(sub, 'alternates', {}).items():
                    if src in names:
                        extra.update(dst)
                for first, ligatures in getattr(sub, 'ligatures', {}).items():
                    for lig in ligatures:
                        if first in names and all(n in names for n in lig.Component):
                            extra.add(lig.LigGlyph)
        extra = {n for n in extra if n in glyf and foot_points(glyf[n], baseline, limit)} - names
        if not extra:
            return names
        names.update(extra)


def align(font):
    glyf = font['glyf']
    baseline = glyf[font.getBestCmap()[ord('H')]].yMin
    names = targets(font, baseline)
    assert all(font.getBestCmap()[ord(c)] in names for c in 'HIl1bdu')
    for name in names:
        g = glyf[name]
        # Move the rounded foot as a unit; leave a neighbouring round bowl or below-mark intact.
        limit = baseline + round(font['head'].unitsPerEm * 0.04)
        for i in foot_points(g, baseline, limit):
            x, y = g.coordinates[i]
            g.coordinates[i] = (x, y - baseline)
        g.recalcBounds(glyf)
    return names


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--src', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.src.resolve() == args.out.resolve():
        parser.error('source and output directories must differ')
    paths = sorted(args.src.glob('FridaySans*.ttf'))
    if not paths:
        parser.error('no Friday Sans TTF files found')
    args.out.mkdir(parents=True, exist_ok=True)
    for path in paths:
        out = args.out / path.name
        if out.exists():
            raise FileExistsError(out)
        font = TTFont(path)
        names = align(font)
        font.save(out)
        print(f'{path.name}: {len(names)} glyphs')


if __name__ == '__main__':
    main()
