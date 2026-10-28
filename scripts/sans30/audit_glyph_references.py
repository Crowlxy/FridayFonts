#!/usr/bin/env python3
"""Compare every shared mapped character with Noto Sans JP and Hiragino, per face.

    python scripts/sans30/audit_glyph_references.py --dir <ttf dir> --out <report dir>

Scores flag visual differences for inspection, not confirmed defects. Reference fonts are read only.
"""
import argparse
import csv
import json
from pathlib import Path
import unicodedata

import freetype
import numpy as np
from PIL import Image
from fontTools.ttLib import TTFont

PX = 64
WEIGHTS = {'Light': 2, 'Regular': 3, 'Medium': 4, 'SemiBold': 5, 'Bold': 6}


class Face:
    def __init__(self, path, index=0):
        self.font = TTFont(path, fontNumber=index)
        self.cmap = self.font.getBestCmap()
        self.face = freetype.Face.from_bytes(path.read_bytes(), index=index)
        self.face.set_pixel_sizes(0, PX)

    def image(self, cp):
        self.face.load_char(chr(cp), freetype.FT_LOAD_RENDER | freetype.FT_LOAD_NO_HINTING)
        slot = self.face.glyph
        bitmap = slot.bitmap
        if not bitmap.width or not bitmap.rows:
            return None
        data = np.array(bitmap.buffer, dtype=np.uint8).reshape(bitmap.rows, abs(bitmap.pitch))[:, :bitmap.width]
        if not np.any(data):
            return None
        mask = Image.fromarray(data).resize((32, 32), Image.Resampling.BILINEAR)
        ink = np.asarray(mask) >= 96
        bounds = (slot.bitmap_left / PX, (slot.bitmap_top - bitmap.rows) / PX,
                  (slot.bitmap_left + bitmap.width) / PX, slot.bitmap_top / PX)
        return ink, bounds, slot.advance.x / (64 * PX)


def difference(a, b):
    intersection = np.count_nonzero(a[0] & b[0])
    union = np.count_nonzero(a[0] | b[0])
    shape = float(1 - intersection / union) if union else 0.0
    position = max(abs(a[1][i] - b[1][i]) for i in range(4))
    advance = abs(a[2] - b[2])
    return shape, position, advance


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--reference', type=Path, default=Path('reference'))
    parser.add_argument('--only', nargs='+', help='specific face names; default is all ten')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    paths = sorted(args.dir.glob('FridaySans*.ttf'))
    if len(paths) != 10:
        parser.error('expected all 10 Friday Sans faces')
    if args.only:
        paths = [path for path in paths if path.stem in args.only]
        if len(paths) != len(set(args.only)):
            parser.error('unknown face name')
    assert difference((np.ones((2, 2), bool), (0, 0, 1, 1), 1),
                      (np.ones((2, 2), bool), (0, 0, 1, 1), 1)) == (0, 0, 0)
    summary = {}
    for path in paths:
        weight = path.stem.split('-')[-1]
        friday = Face(path)
        refs = {
            'noto': Face(args.reference / 'Noto_Sans_JP' / 'static' / f'NotoSansJP-{weight}.ttf'),
            'hiragino': Face(args.reference / 'ヒラノギ角ゴ' / f'ヒラギノ角ゴシック W{WEIGHTS[weight]}.ttc'),
        }
        counts = {}
        for refname, ref in refs.items():
            cps = sorted(cp for cp in friday.cmap.keys() & ref.cmap.keys()
                         if not unicodedata.category(chr(cp)).startswith('C'))
            rows = []
            missing = []
            for cp in cps:
                a, b = friday.image(cp), ref.image(cp)
                if a is None or b is None:
                    if (a is None) != (b is None):
                        missing.append(f'U+{cp:04X}')
                    continue
                shape, position, advance = difference(a, b)
                rows.append((cp, round(shape, 4), round(position, 4), round(advance, 4)))
            csvpath = args.out / f'{path.stem}-{refname}.csv'
            with csvpath.open('w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(('codepoint', 'character', 'name', 'shape_difference', 'max_bound_difference_em', 'advance_difference_em'))
                for cp, shape, position, advance in rows:
                    writer.writerow((f'U+{cp:04X}', chr(cp), unicodedata.name(chr(cp), ''), shape, position, advance))
            counts[refname] = {'shared_non_control': len(cps), 'compared_visible': len(rows),
                               'one_side_empty': missing,
                               'shape_over_0_65': sum(row[1] > 0.65 for row in rows),
                               'bound_over_0_20_em': sum(row[2] > 0.20 for row in rows)}
            print(path.stem, refname, counts[refname], flush=True)
        summary[path.stem] = counts
    (args.out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
