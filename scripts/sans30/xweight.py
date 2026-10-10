#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare a glyph with the same glyph in the neighbouring weights.

    python xweight.py --dir <ttf dir> [--family FridaySans] [--pair Light:Regular] [--json out.json]

verify_sans_30.py compares 3.0 with 2.5, so a defect that 2.5 already had passes.  This
compares weights of one build instead.  Each weight is drawn from its outline (own rasteriser,
no hinting) at PX px per em and the lighter weight is checked against the heavier:

  excess   ink of the lighter weight that lies further than TOL px outside the heavier weight
           (a black wedge, a spur: the lighter face must not carry ink the heavier one lacks)
  missing  core of the heavier weight (eroded by TOL px) that has no ink within TOL px in the
           lighter weight (a stroke that is gone)

A defect is a connected region of at least MIN_AREA px^2 (8 px^2 at 160 px/em, the threshold
used for the 2026-10-09 review).  Weights that differ in stem width by only a few units give
0 regions on a sound glyph; the check does not look at glyphs that are broken in the same way
in both weights.
"""
import argparse
import json
import os
import sys
from multiprocessing import Pool

import numpy as np
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from scipy import ndimage
from skimage.draw import polygon as fill_polygon

PX = 160
TOL = 3          # px at PX px/em: 3 px = 19 units per 1000, more than a weight step's drift
MIN_AREA = int(os.environ.get("XW_MIN_AREA", 8))     # px^2 (workers read the environment)
ORDER = ["Light", "Regular", "Medium", "SemiBold", "Bold"]


class FlatPen(BasePen):
    def __init__(self, gs, scale):
        super().__init__(gs)
        self.k = scale
        self.contours, self.cur = [], []

    def _moveTo(self, p):
        self.cur = [p]

    def _lineTo(self, p):
        self.cur.append(p)

    def _curveToOne(self, a, b, c):
        p0 = self.cur[-1]
        for i in range(1, 9):
            t = i / 8
            u = 1 - t
            self.cur.append((u**3 * p0[0] + 3 * u * u * t * a[0] + 3 * u * t * t * b[0] + t**3 * c[0],
                             u**3 * p0[1] + 3 * u * u * t * a[1] + 3 * u * t * t * b[1] + t**3 * c[1]))

    def _qCurveToOne(self, a, b):
        p0 = self.cur[-1]
        for i in range(1, 7):
            t = i / 6
            u = 1 - t
            self.cur.append((u * u * p0[0] + 2 * u * t * a[0] + t * t * b[0],
                             u * u * p0[1] + 2 * u * t * a[1] + t * t * b[1]))

    def _closePath(self):
        if len(self.cur) > 2:
            self.contours.append(self.cur)
        self.cur = []

    _endPath = _closePath


def raster(font, gs, name, size=PX, box=(-0.25, 1.25)):
    """Boolean ink image of a glyph, em box [box0, box1] x [box0, box1] at `size` px per em."""
    upem = font["head"].unitsPerEm
    k = size / upem
    n = int((box[1] - box[0]) * size)
    pen = FlatPen(gs, k)
    gs[name].draw(pen)
    acc = np.zeros((n, n), dtype=np.int16)
    for c in pen.contours:
        xs = np.array([(p[0] * k - box[0] * size) for p in c])
        ys = np.array([(n - (p[1] * k - box[0] * size)) for p in c])
        a = 0.5 * float(np.sum(xs * np.roll(ys, -1) - np.roll(xs, -1) * ys))
        rr, cc = fill_polygon(ys, xs, (n, n))
        acc[rr, cc] += 1 if a < 0 else -1
    return acc != 0            # non-zero winding, whichever way the outlines are oriented


def regions(mask):
    lab, k = ndimage.label(mask)
    out = []
    for i in range(1, k + 1):
        a = int((lab == i).sum())
        if a >= MIN_AREA:
            ys, xs = np.nonzero(lab == i)
            out.append((a, int(xs.mean()), int(ys.mean())))
    return out


def compare(light, heavy):
    ball = ndimage.iterate_structure(ndimage.generate_binary_structure(2, 1), TOL)
    excess = light & ~ndimage.binary_dilation(heavy, ball)
    core = ndimage.binary_erosion(heavy, ball)
    missing = core & ~ndimage.binary_dilation(light, ball)
    return regions(excess), regions(missing)


def job(args):
    path_lo, path_hi, names = args
    lo, hi = TTFont(path_lo), TTFont(path_hi)
    glo, ghi = lo.getGlyphSet(), hi.getGlyphSet()
    bad = {}
    for n in names:
        if n not in glo or n not in ghi:
            continue
        if lo["glyf"][n].numberOfContours == 0 or hi["glyf"][n].numberOfContours == 0:
            continue
        ex, mi = compare(raster(lo, glo, n), raster(hi, ghi, n))
        if ex or mi:
            bad[n] = {"excess": ex, "missing": mi}
    return bad


def full_cell_glyphs(lo, hi):
    """Kanji, kana and their variants: glyphs drawn on the full em cell, where the weights share
    an origin.  (Latin glyphs have a different side bearing in every weight, so the outlines of
    two weights do not overlay.)"""
    cm = lo.getBestCmap()
    names = {cm[cp] for cp in cm if 0x2E80 <= cp <= 0x9FFF or 0xF900 <= cp <= 0xFAFF}
    full = 0.9 * lo["head"].unitsPerEm
    for n in lo.getGlyphOrder():
        if (n.startswith("jp.") and n in hi.getGlyphOrder() and lo["hmtx"][n][0] == hi["hmtx"][n][0]
                and lo["hmtx"][n][0] >= full):
            names.add(n)
    return sorted(names)


def check_pair(path_lo, path_hi, names=None, procs=None):
    """{glyph name: {"excess": [(area, x, y)], "missing": [...]}} for the glyphs that fail."""
    f = TTFont(path_lo)
    if names is None:
        names = full_cell_glyphs(f, TTFont(path_hi))
    f.close()
    chunks = [names[i::32] for i in range(32)]
    with Pool(procs or min(os.cpu_count() or 4, 12)) as pool:
        parts = pool.map(job, [(path_lo, path_hi, c) for c in chunks])
    out = {}
    for p in parts:
        out.update(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--family", default="FridaySans")
    ap.add_argument("--pair", action="append", default=[])
    ap.add_argument("--json", default="")
    ap.add_argument("--min-area", type=int, default=MIN_AREA)
    a = ap.parse_args()
    os.environ["XW_MIN_AREA"] = str(a.min_area)
    globals()["MIN_AREA"] = a.min_area
    pairs = a.pair or ["%s:%s" % (ORDER[i], ORDER[i + 1]) for i in range(len(ORDER) - 1)]
    res = {}
    for pr in pairs:
        lo, hi = pr.split(":")
        r = check_pair(os.path.join(a.dir, "%s-%s.ttf" % (a.family, lo)),
                       os.path.join(a.dir, "%s-%s.ttf" % (a.family, hi)))
        res[pr] = r
        print("%s %s: %d glyphs" % (a.family, pr, len(r)))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1, ensure_ascii=False)
    return 1 if any(res.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
