#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Proof images for the Friday Sans 3.0 record, drawn from the built faces.

    python proof_sans_30.py --ttf work/sans-3.0/ttf --src work/sans-3.0/x/FridaySans-2.5/ttf --out work/sans-3.0/stage/reports

  weights-proof-FridaySans.png / -FridaySansUI.png   the five weights, kana / kanji / Latin, 14-40 px
  light-repair-before-after.png                      the repaired Light kanji: 2.5 | 3.0 | Regular
  approx-equal.png                                   U+2252 in the five weights beside U+FF1D

PIL with FreeType, grayscale, no hinting for the 3.0 faces (they carry none).  This is not a
ClearType rendering.
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import repair_light as RL  # noqa: E402

WEIGHTS = ["Light", "Regular", "Medium", "SemiBold", "Bold"]
SAMPLE = "日本語の文字組み 共題武昆廃慮 Hamburgefonstiv 0123456789 ≒"


def font(path, size):
    return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.BASIC)


def weights_proof(ttf, fam, out):
    sizes = (14, 20, 28, 40)
    width = 1500
    height = len(WEIGHTS) * (sum(int(s * 1.45) for s in sizes) + 34) + 10
    im = Image.new("L", (width, height), 255)
    d = ImageDraw.Draw(im)
    label = ImageFont.truetype(os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "arial.ttf"), 14)
    y = 8
    for w in WEIGHTS:
        path = os.path.join(ttf, "%s-%s.ttf" % (fam, w))
        d.text((8, y), "%s %s" % (fam, w), font=label, fill=90)
        y += 24
        for s in sizes:
            d.text((8, y), SAMPLE, font=font(path, s), fill=0)
            y += int(s * 1.45)
        y += 10
    im.crop((0, 0, width, y)).save(os.path.join(out, "weights-proof-%s.png" % fam))


def light_repair(ttf, src, out, per_row=12, rows=None, size=104):
    names = RL.load_list()["glyphs"]
    if rows is None:
        rows = (len(names) + per_row - 1) // per_row
    else:
        names = names[:per_row * rows]
    from fontTools.ttLib import TTFont
    cmap = {n: cp for cp, n in TTFont(os.path.join(ttf, "FridaySans-Regular.ttf")).getBestCmap().items()}
    cells = [("2.5 Light", os.path.join(src, "FridaySans-Light.ttf")),
             ("3.0 Light", os.path.join(ttf, "FridaySans-Light.ttf")),
             ("3.0 Regular", os.path.join(ttf, "FridaySans-Regular.ttf"))]
    cw = size + 6
    im = Image.new("L", (per_row * cw, rows * (3 * cw + 6)), 255)
    d = ImageDraw.Draw(im)
    for i, n in enumerate(names):
        ch = chr(cmap[n]) if n in cmap else "?"
        col, row = i % per_row, i // per_row
        for j, (_, path) in enumerate(cells):
            d.text((col * cw, row * (3 * cw + 6) + j * cw), ch, font=font(path, size - 8), fill=0)
    im.save(os.path.join(out, "light-repair-before-after.png"))


def approx_equal(ttf, out, size=150):
    im = Image.new("L", (5 * (size * 2 + 20), size + 30), 255)
    d = ImageDraw.Draw(im)
    for i, w in enumerate(WEIGHTS):
        d.text((i * (size * 2 + 20), 4), "\u2252\uff1d", font=font(os.path.join(ttf, "FridaySans-%s.ttf" % w), size), fill=0)
    im.save(os.path.join(out, "approx-equal.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ttf", required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for fam in ("FridaySans", "FridaySansUI"):
        weights_proof(a.ttf, fam, a.out)
    light_repair(a.ttf, a.src, a.out)
    approx_equal(a.ttf, a.out)


if __name__ == "__main__":
    main()
