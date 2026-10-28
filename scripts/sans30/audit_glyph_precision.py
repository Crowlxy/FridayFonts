#!/usr/bin/env python3
"""Compare each shared character at 160 px, including precise bounds and local ink differences."""
import argparse
import ctypes
import csv
import json
from pathlib import Path
import unicodedata

import freetype
import numpy as np
from PIL import Image
from scipy import ndimage
from fontTools.ttLib import TTFont

PX, MASK = 160, 96
WEIGHTS = {'Light': 2, 'Regular': 3, 'Medium': 4, 'SemiBold': 5, 'Bold': 6}


class Face:
    def __init__(self, path):
        self.tt = TTFont(path, fontNumber=0)
        self.cmap = self.tt.getBestCmap()
        self.em = self.tt['head'].unitsPerEm
        self.face = freetype.Face.from_bytes(path.read_bytes())
        self.face.set_pixel_sizes(0, PX)

    def glyph(self, cp):
        face = self.face
        face.load_char(chr(cp), freetype.FT_LOAD_NO_SCALE | freetype.FT_LOAD_NO_HINTING)
        m = face.glyph.metrics
        bbox = (m.horiBearingX / self.em, (m.horiBearingY - m.height) / self.em,
                (m.horiBearingX + m.width) / self.em, m.horiBearingY / self.em)
        advance = m.horiAdvance / self.em
        face.load_char(chr(cp), freetype.FT_LOAD_RENDER | freetype.FT_LOAD_NO_HINTING)
        bitmap = face.glyph.bitmap
        if not bitmap.width or not bitmap.rows:
            return None
        assert bitmap.pitch > 0
        raw = np.frombuffer(ctypes.string_at(bitmap._FT_Bitmap.buffer, bitmap.rows * bitmap.pitch),
                            dtype=np.uint8).reshape(bitmap.rows, bitmap.pitch)[:, :bitmap.width]
        if not np.any(raw):
            return None
        image = Image.fromarray(raw).resize((MASK, MASK), Image.Resampling.BILINEAR)
        return np.asarray(image) >= 96, bbox, advance


def largest(mask):
    labels, count = ndimage.label(mask)
    if not count:
        return 0
    return int(np.bincount(labels.ravel())[1:].max())


def compare(a, b):
    am, ab, aa = a
    bm, bb, ba = b
    union = np.count_nonzero(am | bm)
    shape = 1.0 - np.count_nonzero(am & bm) / union if union else 0.0
    # A one-pixel tolerance suppresses harmless rounding when masks are normalized to 96 px.
    extra = am & ~ndimage.binary_dilation(bm, iterations=1)
    missing = bm & ~ndimage.binary_dilation(am, iterations=1)
    return (float(shape), max(abs(x - y) for x, y in zip(ab, bb)), abs(aa - ba),
            float(np.count_nonzero(extra) / max(1, np.count_nonzero(am))),
            float(np.count_nonzero(missing) / max(1, np.count_nonzero(bm))),
            largest(extra), largest(missing))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--reference', type=Path, default=Path('reference'))
    parser.add_argument('--only', nargs='+')
    args = parser.parse_args()
    paths = sorted(args.dir.glob('FridaySans*.ttf'))
    if len(paths) != 10:
        parser.error('expected all ten Friday Sans faces')
    if args.only:
        paths = [p for p in paths if p.stem in args.only]
        if len(paths) != len(set(args.only)):
            parser.error('unknown face')
    args.out.mkdir(parents=True, exist_ok=True)
    blank = np.ones((MASK, MASK), dtype=bool)
    assert compare((blank, (0, 0, 1, 1), 1), (blank, (0, 0, 1, 1), 1)) == (0, 0, 0, 0, 0, 0, 0)
    summary = {}
    for path in paths:
        weight = path.stem.split('-')[-1]
        friday = Face(path)
        references = {
            'noto': Face(args.reference / 'Noto_Sans_JP' / 'static' / f'NotoSansJP-{weight}.ttf'),
            'hiragino': Face(args.reference / 'ヒラノギ角ゴ' / f'ヒラギノ角ゴシック W{WEIGHTS[weight]}.ttc'),
        }
        summary[path.stem] = {}
        for label, reference in references.items():
            common = sorted(cp for cp in friday.cmap.keys() & reference.cmap.keys()
                            if not unicodedata.category(chr(cp)).startswith('C'))
            rows, empty = [], []
            for cp in common:
                a, b = friday.glyph(cp), reference.glyph(cp)
                if a is None or b is None:
                    if (a is None) != (b is None):
                        empty.append(f'U+{cp:04X}')
                    continue
                rows.append((cp, *compare(a, b)))
            with (args.out / f'{path.stem}-{label}.csv').open('w', encoding='utf-8', newline='') as fh:
                writer = csv.writer(fh)
                writer.writerow(('codepoint', 'character', 'name', 'shape_difference', 'max_bound_difference_em',
                                 'advance_difference_em', 'extra_ink_fraction', 'missing_ink_fraction',
                                 'largest_extra_region', 'largest_missing_region'))
                for cp, *values in rows:
                    writer.writerow((f'U+{cp:04X}', chr(cp), unicodedata.name(chr(cp), ''),
                                     *(round(float(x), 5) for x in values)))
            summary[path.stem][label] = {'shared': len(common), 'compared': len(rows), 'one_side_empty': empty}
            print(path.stem, label, summary[path.stem][label], flush=True)
    (args.out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
