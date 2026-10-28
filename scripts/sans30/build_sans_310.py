#!/usr/bin/env python3
"""Build Friday Sans 3.1.0 from the hash-verified released 3.002 TTFs."""
import argparse
from copy import deepcopy
import hashlib
import json
from multiprocessing import Pool
from pathlib import Path
import sys

from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import align_baseline
import fix_circled_symbols
import localize_ellipsis

VERSION = '3.100'  # OpenType revision for product version 3.1.0.
MANIFEST = Path(__file__).resolve().parents[2] / 'releases/sans-3.0/font-manifest.json'


def fix_long_dashes(font):
    cmap, glyf = font.getBestCmap(), font['glyf']
    emdash = cmap[0x2014]
    source = glyf[emdash]
    assert source.numberOfContours > 0
    advance = font['hmtx'][emdash][0]
    midpoint = (source.xMin + source.xMax) / 2
    for cp, length in ((0x2E3A, 2), (0x2E3B, 3)):
        name = cmap[cp]
        old = glyf[name]
        vertical_origin = old.yMax + font['vmtx'][name][1]
        glyph = deepcopy(source)
        for i, (x, y) in enumerate(glyph.coordinates):
            if x > midpoint:
                glyph.coordinates[i] = (x + (length - 1) * advance, y)
        glyph.recalcBounds(glyf)
        glyf[name] = glyph
        font['hmtx'][name] = (length * advance, glyph.xMin)
        font['vmtx'][name] = (font['vmtx'][name][0], vertical_origin - glyph.yMax)


def build_one(job):
    src, dst = job
    font = TTFont(src)
    assert font['name'].getDebugName(5) == 'Version 3.002'
    baseline = len(align_baseline.align(font))
    localize_ellipsis.localize(font)
    circled = len(fix_circled_symbols.fix(font))
    fix_long_dashes(font)
    font['head'].fontRevision = float(VERSION)
    for record in font['name'].names:
        if record.nameID == 3:
            value = record.toUnicode()
            assert '3.002' in value
            record.string = value.replace('3.002', VERSION)
        elif record.nameID == 5:
            record.string = 'Version ' + VERSION
    font.save(dst)
    return Path(dst).name, baseline, circled


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--src', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.src.resolve() == args.out.resolve():
        parser.error('source and output directories must differ')
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    jobs = []
    for item in manifest:
        name = Path(item['ttf']).name
        src, dst = args.src / name, args.out / name
        if not src.is_file() or hashlib.sha256(src.read_bytes()).hexdigest() != item['sha256']:
            parser.error(f'3.002 input missing or hash mismatch: {src}')
        if dst.exists():
            parser.error(f'output already exists: {dst}')
        jobs.append((str(src), str(dst)))
    assert len(jobs) == 10
    args.out.mkdir(parents=True, exist_ok=True)
    with Pool(4) as pool:
        for name, baseline, circled in pool.imap_unordered(build_one, jobs):
            print(name, 'baseline', baseline, 'circled', circled, flush=True)


if __name__ == '__main__':
    main()
