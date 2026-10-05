#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Show that Friday Sans does not use SF Pro's or Hiragino's outlines.

    python make_overlay.py [--style Regular]

Prints, per character, how much of each glyph's ink overlaps the same glyph
in the font Friday Sans was built from (Inter / Noto Sans CJK JP) and in the
font it was measured against (SF Pro Text / Hiragino Sans).  Glyphs are
rasterised at the same height and centred on their own ink, so the figure is
about shape alone, not size or position: 1.0 is the identical outline.

Writes work/friday-sans-overlay.png (local only, never committed: it shows
SF Pro and Hiragino glyphs): black where both agree, blue where
only Friday Sans has ink, red where only the reference does.

SF Pro and Hiragino are read from this machine for the measurement only;
neither file is part of the repository or of any release.
"""
import argparse
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "Source"))
INTER = os.path.join(SRC, "Inter", "Inter-4.1", "InterVariable.ttf")
NOTO = os.path.join(SRC, "noto-cjk", "NotoSansCJKjp-VF.ttf")
SF = "/Library/Fonts/SF-Pro-Text-%s.otf"
HIRA = os.path.join(SRC, "Hiragino Sans", "ヒラギノ角ゴシック %s.ttc")
LATIN = "aegtyRGQJ1$&@"
CJK = "永国書東語機鬱あいうえお"
PAIRS = {"Regular": ("Regular", "W3"), "Medium": ("Medium", "W4"), "Bold": ("Semibold", "W6")}
PX = 300


def ink(path, ch, index=0):
    font = ImageFont.truetype(path, PX, index=index)
    mask = font.getmask(ch)
    a = np.array(Image.frombytes("L", mask.size, bytes(mask)), dtype=float) / 255.0
    ys, xs = np.nonzero(a > 0.5)
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def fit(a, h, w):
    """Scale to a common ink height, then centre on a common canvas."""
    img = Image.fromarray((a * 255).astype("uint8"))
    s = h / img.height
    img = img.resize((max(1, round(img.width * s)), h), Image.LANCZOS)
    out = np.zeros((h, w))
    x = (w - img.width) // 2
    out[:, max(0, x):max(0, x) + min(w, img.width)] = np.array(img)[:, :min(w, img.width)] / 255.0
    return out


def compare(fa, fb, ch, ia=0, ib=0):
    a, b = ink(fa, ch, ia), ink(fb, ch, ib)
    h = 240
    w = int(max(a.shape[1] * h / a.shape[0], b.shape[1] * h / b.shape[0])) + 8
    a, b = fit(a, h, w) > 0.5, fit(b, h, w) > 0.5
    return (a & b).sum() / (a | b).sum(), a, b


def tile(a, b):
    img = np.ones(a.shape + (3,))
    both, ao, bo = a & b, a & ~b, b & ~a
    img[both] = (0, 0, 0)
    img[ao] = (0.0, 0.45, 1.0)
    img[bo] = (1.0, 0.0, 0.0)
    return Image.fromarray((img * 255).astype("uint8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", default="Regular")
    args = ap.parse_args()
    sf_w, hira_w = PAIRS[args.style]
    friday = os.path.join(HERE, "fonts", "FridaySans-%s.ttf" % args.style)
    # The exact source instances this face was cut from.
    work = os.path.join(HERE, "work")
    os.makedirs(work, exist_ok=True)
    fr = TTFont(friday)
    from build_sans import FRIDAY_STEM, solve_wght, inter_scale  # noqa: E402
    _, s, _ = inter_scale()
    wght, _ = solve_wght(args.style, s)
    inter = os.path.join(work, "Inter-%s.ttf" % args.style)
    instancer.instantiateVariableFont(TTFont(INTER), {"opsz": 14, "wght": wght}).save(inter)
    import pickle
    with open(os.path.join(work, "cjk-%s.pkl" % args.style), "rb") as fh:
        kanji_wght = pickle.load(fh)["report"]["source_wght"]["kanji"]
    noto = os.path.join(work, "Noto-%s.ttf" % args.style)
    instancer.instantiateVariableFont(TTFont(NOTO), {"wght": kanji_wght}).save(noto)
    fr.close()

    rows, labels = [], []
    for chars, src, src_name, ref, ref_idx, ref_name in (
            (LATIN, inter, "Inter", SF % sf_w, 0, "SF Pro Text %s" % sf_w),
            (CJK, noto, "Noto", HIRA % hira_w, 0, "ヒラギノ角ゴ %s" % hira_w)):
        own, other, tiles = [], [], []
        print("%s: vs %s / vs %s" % (args.style, src_name, ref_name))
        for ch in chars:
            i1, _, _ = compare(friday, src, ch)
            i2, a, b = compare(friday, ref, ch, 0, ref_idx)
            own.append(i1)
            other.append(i2)
            tiles.append(tile(a, b))
            print("  %s  %.3f / %.3f" % (ch, i1, i2))
        print("  mean %.3f / %.3f" % (np.mean(own), np.mean(other)))
        rows.append(tiles)
        labels.append("Friday Sans %s と %s の重ね合わせ（形の一致度 平均 %.2f。%s とは %.2f）"
                      % (args.style, ref_name, np.mean(other), src_name, np.mean(own)))

    pad, scale = 30, 0.5
    rows = [[t.resize((int(t.width * scale), int(t.height * scale))) for t in r] for r in rows]
    label_font = ImageFont.truetype(HIRA % "W3", 20, index=0)
    width = max(sum(t.width for t in r) + pad * (len(r) + 1) for r in rows) + 20
    height = 60 + sum(max(t.height for t in r) + 2 * pad + 36 for r in rows)
    out = Image.new("RGB", (width, height), "white")
    d = ImageDraw.Draw(out)
    d.text((20, 14), "黒＝両方に共通　青＝Friday Sans だけ　赤＝参照フォントだけ",
           font=label_font, fill=(40, 40, 40))
    y = 56
    for r, text in zip(rows, labels):
        d.text((20, y), text, font=label_font, fill=(90, 90, 90))
        y += 34
        x = 20
        h = max(t.height for t in r)
        for t in r:
            out.paste(t, (x, y + (h - t.height) // 2))
            x += t.width + pad
        y += h + 2 * pad
    dest = os.path.join(HERE, "work", "friday-sans-overlay.png")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    out.save(dest)
    print("wrote", dest, out.size)


if __name__ == "__main__":
    main()
