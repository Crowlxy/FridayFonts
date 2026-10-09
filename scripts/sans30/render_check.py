#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render every encoded glyph of every face with FreeType (Pillow) at small sizes.

    python render_check.py --out <3.0 ttf dir>

Fails on a render error, an empty raster for a glyph that has ink, or a raster whose
height is under half of the design height (the "flattened glyph" failure of broken hints).
"""
import argparse
import glob
import os
import sys
from multiprocessing import Pool

from fontTools.ttLib import TTFont
from PIL import ImageFont

SIZES = (9, 12, 16, 24)


def check(path):
    f = TTFont(path)
    upem = f["head"].unitsPerEm
    g = f["glyf"]
    cm = f.getBestCmap()
    todo = [(cp, n) for cp, n in cm.items() if g[n].numberOfContours and cp not in (0x20, 0xA0)]
    bad = []
    for px in SIZES:
        face = ImageFont.truetype(path, px, layout_engine=ImageFont.Layout.BASIC)
        for cp, n in todo:
            try:
                box = face.getmask(chr(cp)).getbbox()
            except Exception as ex:           # noqa: BLE001
                bad.append((px, hex(cp), "error " + str(ex)[:40]))
                continue
            design = (g[n].yMax - g[n].yMin) * px / upem
            if design >= 3 and (box is None or (box[3] - box[1]) < design * 0.5):
                bad.append((px, hex(cp), "flat/empty"))
    return os.path.basename(path), len(todo), bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    paths = sorted(glob.glob(os.path.join(a.out, "*.ttf")))
    with Pool(min(len(paths), 10)) as pool:
        res = pool.map(check, paths)
    fail = 0
    for name, n, bad in res:
        print(name, n, "glyphs x", len(SIZES), "sizes:", "OK" if not bad else "%d problems %s" % (len(bad), bad[:6]))
        fail += len(bad)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
