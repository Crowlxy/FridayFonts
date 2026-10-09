#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Per-glyph audit of what removing the hints costs, against reference faces.

    python audit_unhinted.py --out audit.json

Faces (all Regular, all rasterised the same way, without hinting):
  Friday Sans 3.0, Friday Sans 2.5 (outlines), Hiragino Sans W3, Noto Sans JP (wght 400),
  Inter (opsz 14, wght 400; Latin only), SF Pro Text Regular (Latin only).
Reference files are read for measurement only.

Per glyph (never averaged over the face before the spread is taken):
  stems   median vertical-stem and horizontal-stroke width, as a ratio to the median of its class
  crisp   E = sum(C^2)/sum(C) of the anti-aliased raster (1 = solid pixels, 0.5 = grey smear),
          mean over four sub-pixel phases, at 12 / 14 / 16 px;  phase range = max - min over phases
  height  top and bottom of the ink in pixels at 12 / 14 / 16 px, against the class reference line
"""
import argparse
import json
import math
import os
import random
import statistics
import sys

import numpy as np
import pathops
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from PIL import Image, ImageDraw, ImageFont

ROOT = os.getcwd()
FACES = {
    "Friday Sans 3.0": ("ttf/FridaySans-Regular.ttf", 0, True),
    "Friday Sans UI 3.0": ("ttf/FridaySansUI-Regular.ttf", 0, True),
    "Friday Sans 2.5": ("x/FridaySans-2.5/ttf/FridaySans-Regular.ttf", 0, True),
    "Hiragino W3": ("cmp/hira_w3.ttc", 0, True),
    "Noto Sans JP": ("cmp/noto400.ttf", 0, True),
    "Inter": ("cmp/inter400.ttf", 0, False),
    "SF Pro Text": ("cmp/sf_text.otf", 0, False),
}
SS = 8                      # supersampling for the anti-aliased raster
SIZES = (12, 14, 16)
PHASES = ((0.0, 0.0), (0.5, 0.0), (0.0, 0.5), (0.5, 0.5))

LOWER = "abcdefghijklmnopqrstuvwxyz"
UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DIGITS = "0123456789"
HIRA = [chr(c) for c in range(0x3041, 0x3094)]
KATA = [chr(c) for c in range(0x30A1, 0x30F7)]


def jis1_kanji():
    out = []
    for lead in range(0x88, 0x99):
        for trail in range(0x40, 0xFD):
            try:
                ch = bytes([lead, trail]).decode("shift_jis")
            except UnicodeDecodeError:
                continue
            if len(ch) == 1 and 0x4E00 <= ord(ch) <= 0x9FFF:
                out.append(ch)
    return out


def flatten(rec, upem):
    """Contours as arrays of (x, y) in em units (y up)."""
    cons, cur, pos = [], None, None

    def q(p0, c, p1, n=8):
        t = np.linspace(0, 1, n + 1)[1:, None]
        return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * c + t ** 2 * p1

    def cb(p0, c1, c2, p1, n=10):
        t = np.linspace(0, 1, n + 1)[1:, None]
        return ((1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * c1 + 3 * (1 - t) * t ** 2 * c2 + t ** 3 * p1)

    for op, args in rec.value:
        if op == "moveTo":
            pos = np.array(args[0], float)
            cur = [pos]
        elif op == "lineTo":
            pos = np.array(args[0], float)
            cur.append(pos)
        elif op == "qCurveTo" and args[-1] is None:      # closed contour of off-curve points only
            offs = [np.array(a, float) for a in args[:-1]]
            m = len(offs)
            mids = [(offs[i] + offs[(i + 1) % m]) / 2 for i in range(m)]
            cur = [mids[-1]]
            for i in range(m):
                cur.extend(list(q(mids[i - 1], offs[i], mids[i])))
            pos = mids[-1]
        elif op == "qCurveTo":
            pts = [np.array(a, float) for a in args if a is not None]
            offs, end = pts[:-1], pts[-1]
            p0 = pos
            for i, c in enumerate(offs):
                nxt = end if i == len(offs) - 1 else (c + offs[i + 1]) / 2
                cur.extend(list(q(p0, c, nxt)))
                p0 = nxt
            pos = end
        elif op == "curveTo":
            c1, c2, e = (np.array(a, float) for a in args)
            cur.extend(list(cb(pos, c1, c2, e)))
            pos = e
        elif op in ("closePath", "endPath"):
            cons.append(np.array(cur) / upem)
            cur = None
    return cons


def area(c):
    x, y = c[:, 0], c[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


class Face:
    def __init__(self, name, path, index):
        self.name = name
        self.font = TTFont(os.path.join(ROOT, path), fontNumber=index)
        self.upem = self.font["head"].unitsPerEm
        self.cmap = self.font.getBestCmap()
        self.gs = self.font.getGlyphSet()
        self.cache = {}

    def has(self, ch):
        return ord(ch) in self.cmap

    def contours(self, ch):
        if ch in self.cache:
            return self.cache[ch]
        p = pathops.Path()
        self.gs[self.cmap[ord(ch)]].draw(p.getPen(glyphSet=self.gs))
        p.simplify(fix_winding=True, keep_starting_points=False, clockwise=True)
        rec = RecordingPen()
        p.draw(rec)
        cons = flatten(rec, self.upem)
        cons.sort(key=lambda c: -abs(area(c)))
        self.cache[ch] = cons
        return cons


def paint(cons, scale, dx, dy, W, H, base, ss=SS):
    """Anti-aliased coverage (0..1), baseline at row `base`, shifted by (dx, dy) pixels."""
    im = Image.new("L", (W * ss, H * ss), 0)
    d = ImageDraw.Draw(im)
    for c in cons:
        pts = [((x * scale + dx + 1) * ss, (base - y * scale + dy) * ss) for x, y in c]
        d.polygon(pts, fill=255 if area(c) < 0 else 0)      # clockwise (area<0) = ink, ccw = hole
    arr = np.asarray(im, dtype=np.float32) / 255.0
    return arr.reshape(H, ss, W, ss).mean(axis=(1, 3)) if ss > 1 else arr


def raster_stats(face, ch, px):
    cons = face.contours(ch)
    if not cons:
        return None
    W = int(math.ceil(1.4 * px)) + 3
    H = int(math.ceil(1.5 * px)) + 3
    base = int(1.1 * px) + 1
    Es, tops, bots, masses = [], [], [], []
    for dx, dy in PHASES:
        C = paint(cons, px, dx, dy, W, H, base)
        s1 = float(C.sum())
        if s1 <= 0:
            return None
        Es.append(float((C * C).sum()) / s1)
        masses.append(s1)
    return dict(E=float(np.mean(Es)), Erange=max(Es) - min(Es), mass=float(np.mean(masses)))


def runs(a):
    out = []
    for row in a:
        r = 0
        for v in list(row) + [False]:
            if v:
                r += 1
            elif r:
                out.append(r)
                r = 0
    return out


def stem_stats(face, ch, S=300):
    cons = face.contours(ch)
    if not cons:
        return None
    W = int(1.4 * S)
    H = int(1.5 * S)
    base = int(1.1 * S)
    a = paint(cons, S, 0, 0, W, H, base, ss=1) > 0.5
    lim = (int(0.02 * S), int(0.2 * S))
    v = [r for r in runs(a) if lim[0] <= r <= lim[1]]
    h = [r for r in runs(a.T) if lim[0] <= r <= lim[1]]
    if not v or not h:
        return None
    return statistics.median(v) / S, statistics.median(h) / S


def bounds(face, ch):
    cons = face.contours(ch)
    if not cons:
        return None
    pts = np.vstack(cons)
    return float(pts[:, 1].max()), float(pts[:, 1].min()), float(pts[:, 0].max() - pts[:, 0].min())


def spread(vals):
    v = np.array(vals, float)
    med = float(np.median(v))
    dev = np.abs(v - med) / med if med else v * 0
    return dict(n=len(v), median=round(med, 4), cv=round(float(v.std() / med), 4) if med else None,
                p5=round(float(np.percentile(v, 5) / med), 3), p95=round(float(np.percentile(v, 95) / med), 3),
                max_dev=round(float(dev.max()), 3), over10=int((dev > 0.10).sum()), over20=int((dev > 0.20).sum()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--kanji", type=int, default=500)
    a = ap.parse_args()
    random.seed(7)
    kanji = jis1_kanji()
    ksample = random.sample(kanji, a.kanji)
    classes = {
        "lower": list(LOWER), "upper": list(UPPER), "digit": list(DIGITS),
        "hiragana": HIRA, "katakana": KATA, "kanji": ksample,
    }
    report = {}
    for name, (path, idx, has_jp) in FACES.items():
        face = Face(name, path, idx)
        rep = {"stems_v": {}, "stems_h": {}, "crisp": {}, "phase_range": {}, "height": {}}
        for cname, chars in classes.items():
            chars = [c for c in chars if face.has(c)]
            if cname in ("hiragana", "katakana", "kanji") and not has_jp:
                continue
            if not chars:
                continue
            st = {c: stem_stats(face, c) for c in chars}
            st = {c: v for c, v in st.items() if v}
            rep["stems_v"][cname] = spread([v[0] for v in st.values()])
            rep["stems_h"][cname] = spread([v[1] for v in st.values()])
            for px in SIZES:
                rs = {c: raster_stats(face, c, px) for c in chars}
                rs = {c: v for c, v in rs.items() if v}
                rep["crisp"].setdefault(cname, {})[px] = spread([v["E"] for v in rs.values()])
                pr = np.array([v["Erange"] for v in rs.values()])
                rep["phase_range"].setdefault(cname, {})[px] = dict(
                    median=round(float(np.median(pr)), 4), p95=round(float(np.percentile(pr, 95)), 4),
                    max=round(float(pr.max()), 4))
            bs = {c: bounds(face, c) for c in chars}
            bs = {c: v for c, v in bs.items() if v}
            if cname in ("lower", "upper", "digit"):
                tops = {c: v[0] for c, v in bs.items()}
                rep["height"][cname] = {c: round(t, 4) for c, t in tops.items()}
            else:
                hs = [v[0] - v[1] for v in bs.values()]
                rep["height"][cname] = spread(hs)
        # vertical position of flat and round tops, in em
        for k, ch in (("x_flat", "x"), ("o_round", "o"), ("H_flat", "H"), ("O_round", "O"), ("zero", "0"), ("one", "1")):
            b = bounds(face, ch)
            rep["height"][k] = dict(top=round(b[0], 4), bottom=round(b[1], 4)) if b else None
        report[name] = rep
        print("done", name, flush=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
