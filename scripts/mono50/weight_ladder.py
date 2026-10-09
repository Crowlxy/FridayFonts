"""Neighbouring weights must draw the same shape (upright faces).

A glyph that is broken in one weight cannot be found by comparing a face with
its own input: the input is broken the same way.  4.93 Light drew the
denominator of U+00BD as a small angle and every check of 5.0 and 5.0.1
passed.  What shows it is the next weight: the ink of the lighter face must
lie within a few pixels of the heavier face's ink, and the other way round.

Each glyph is drawn at 160 px/em in the five upright weights.  For each pair
of neighbours, the largest connected piece of ink that lies farther than 4 px
from the other weight's ink (after a 1 px erosion that drops edge noise) is
measured, both ways.  Noise in 5.0.2 is at most 23 px for every glyph but
U+00BD; a broken one is in the hundreds.  LIMIT is 100.

The italic faces are left out: their weights differ in design (the slant of
Greek and Cyrillic capitals moves by more than 4 px between Regular and
Medium), so the same test would flag drawings that are meant.
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

WEIGHTS = ['Light', 'Regular', 'Medium', 'SemiBold', 'Bold']
PX = 160
NEAR = 4
LIMIT = 100


def _disc(r):
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


D_NEAR, D_ONE = _disc(NEAR), _disc(1)


def _render(font, ch):
    im = Image.new('L', (int(PX * 1.5), int(PX * 1.6)), 0)
    ImageDraw.Draw(im).text((int(PX * 0.2), int(PX * 1.15)), ch, font=font, fill=255, anchor='ls')
    return np.array(im) > 127


def _largest(mask):
    lab, n = ndi.label(mask)
    return int(np.bincount(lab.ravel())[1:].max()) if n else 0


def _job(args):
    folder, codepoints = args
    fonts = []
    for w in WEIGHTS:
        name = 'FridayMono-%s.ttf' % ('Regular' if w == 'Regular' else w)
        fonts.append(ImageFont.truetype(os.path.join(folder, name), PX, layout_engine=ImageFont.Layout.BASIC))
    found = {}
    for cp in codepoints:
        ink = [_render(f, chr(cp)) for f in fonts]
        worst = 0
        for i in range(4):
            a = ndi.binary_erosion(ink[i] & ~ndi.binary_dilation(ink[i + 1], D_NEAR), D_ONE)
            b = ndi.binary_erosion(ink[i + 1] & ~ndi.binary_dilation(ink[i], D_NEAR), D_ONE)
            worst = max(worst, _largest(a), _largest(b))
        if worst:
            found[cp] = worst
    return found


def scan(folder, cmap, workers=8):
    """{code point: size of the largest unmatched piece} for every glyph over LIMIT."""
    from multiprocessing import Pool
    cps = sorted(c for c in cmap if c > 0x20 and not 0x7F <= c < 0xA0)
    jobs = [(str(folder), cps[i::48]) for i in range(48)]
    out = {}
    with Pool(workers) as pool:
        for part in pool.imap_unordered(_job, jobs):
            out.update(part)
    return out
