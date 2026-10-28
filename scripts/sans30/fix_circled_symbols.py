#!/usr/bin/env python3
"""Fit oversized circled digits and operators to the face's own enclosed digit."""
import argparse
from pathlib import Path

from fontTools.misc.roundTools import otRound
from fontTools.ttLib import TTFont

DIGITS = (0x24EA, *range(0x2780, 0x2789))
OPERATORS = tuple(range(0x2295, 0x2299))
# Enclosed numbers and letters already match the reference diameter; the UI faces
# only need them centred in the advance (they sat 27 units left of centre).
ENCLOSED = (*range(0x2460, 0x2474), *range(0x24B6, 0x24EA))


def targets(font):
    cmap = font.getBestCmap()
    result = {cmap[cp]: 1.0 for cp in DIGITS}
    result.update({cmap[cp]: 0.8 for cp in OPERATORS})
    for cp in ENCLOSED:
        if cp in cmap:
            result.setdefault(cmap[cp], 1.0)
    table = font['GSUB'].table
    for feature in table.FeatureList.FeatureRecord:
        if feature.FeatureTag != 'ss05':
            continue
        for index in feature.Feature.LookupListIndex:
            for sub in table.LookupList.Lookup[index].SubTable:
                sub = getattr(sub, 'ExtSubTable', sub)
                for source, dest in getattr(sub, 'mapping', {}).items():
                    number = source.split('.')[0] in ('zero', 'one', 'two', 'three', 'four',
                                                      'five', 'six', 'seven', 'eight', 'nine')
                    ratio = 1.0 if len(source) == 1 and source in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' or number else 0.8
                    if dest in result:
                        assert result[dest] == ratio, (source, dest)
                    result[dest] = ratio
    return result


def fix(font):
    cmap, glyf = font.getBestCmap(), font['glyf']
    reference = glyf[cmap[0x2460]]
    advance = font['hmtx'][cmap[0x2460]][0]
    diameter = reference.xMax - reference.xMin
    center_y = (reference.yMin + reference.yMax) / 2
    names = targets(font)
    assert len(names) >= len(DIGITS + OPERATORS)
    for name, ratio in names.items():
        glyph = glyf[name]
        assert glyph.numberOfContours > 0
        center_x = (glyph.xMin + glyph.xMax) / 2
        old_center_y = (glyph.yMin + glyph.yMax) / 2
        scale = diameter * ratio / (glyph.xMax - glyph.xMin)
        vertical_origin = font['vmtx'][name][1] + glyph.yMax
        for i, (x, y) in enumerate(glyph.coordinates):
            glyph.coordinates[i] = (otRound((x - center_x) * scale + advance / 2),
                                    otRound((y - old_center_y) * scale + center_y))
        glyph.recalcBounds(glyf)
        font['hmtx'][name] = (advance, glyph.xMin)
        font['vmtx'][name] = (font['vmtx'][name][0], vertical_origin - glyph.yMax)
        assert 0 <= glyph.xMin < glyph.xMax <= advance
    return names


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--src', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.src.resolve() == args.out.resolve():
        parser.error('source and output directories must differ')
    paths = sorted(args.src.glob('FridaySans*.ttf'))
    if len(paths) != 10:
        parser.error('expected all ten Friday Sans faces')
    args.out.mkdir(parents=True, exist_ok=True)
    for path in paths:
        output = args.out / path.name
        if output.exists():
            raise FileExistsError(output)
        font = TTFont(path)
        names = fix(font)
        font.save(output)
        print(path.name, len(names), 'glyphs', flush=True)


if __name__ == '__main__':
    main()
