#!/usr/bin/env python3
"""Record every glyph's rendering and every mapped character in a set of TTFs."""
import argparse
import csv
from pathlib import Path
import unicodedata

import freetype
from fontTools.ttLib import TTFont


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    paths = sorted(args.dir.glob('FridaySans*.ttf'))
    if len(paths) != 10:
        parser.error('expected all ten Friday Sans faces')
    args.out.mkdir(parents=True, exist_ok=True)
    for path in paths:
        font = TTFont(path)
        cmap = font.getBestCmap()
        encoded = {}
        for cp, name in cmap.items():
            encoded.setdefault(name, []).append(cp)
        face = freetype.Face.from_bytes(path.read_bytes())
        face.set_pixel_sizes(0, 64)
        rows = []
        for index, name in enumerate(font.getGlyphOrder()):
            face.load_glyph(index, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_NO_HINTING)
            bitmap = face.glyph.bitmap
            visible = bool(bitmap.width and bitmap.rows and any(bitmap.buffer))
            advance, lsb = font['hmtx'][name]
            glyph = font['glyf'][name]
            if glyph.numberOfContours:
                glyph.recalcBounds(font['glyf'])
                left, right = glyph.xMin, glyph.xMax
            else:
                left = right = 0
            codes = encoded.get(name, [])
            rows.append((index, name, ' '.join(f'U+{cp:04X}' for cp in codes),
                         ' '.join(unicodedata.category(chr(cp)) for cp in codes),
                         int(visible), advance, left, right))
        assert len(rows) == len(font.getGlyphOrder()) and sum(len(x) for x in encoded.values()) == len(cmap)
        with (args.out / f'{path.stem}-glyphs.csv').open('w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(('glyph_id', 'glyph_name', 'codepoints', 'categories', 'visible_64px', 'advance', 'xmin', 'xmax'))
            writer.writerows(rows)
        print(path.stem, len(rows), 'glyphs;', len(cmap), 'mapped characters;',
              sum(not row[4] for row in rows), 'empty glyphs', flush=True)


if __name__ == '__main__':
    main()
