#!/usr/bin/env python3
"""Stage-1 proof: Friday Sans CJK against Hiragino Sans, same em, same size."""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
HIRA = os.path.join(HERE, "..", "..", "..", "Source", "Hiragino Sans", "ヒラギノ角ゴシック %s.ttc")
LINES = ["吾輩は猫である。名前はまだ無い。どこで生れたかとんと見当がつかぬ。",
         "さきやふと、ざぎゃぶぷど。アイウエオ「カタカナ」※①○→★…",
         "東京都千代田区丸の内一丁目、令和八年十月一日（木）午前九時。"]
PAIRS = [("Regular", "W3"), ("Medium", "W4"), ("Bold", "W6")]
PX, PAD, GAP = 34, 28, 14

def main():
    rows = []
    for style, w in PAIRS:
        rows.append(("Hiragino Sans %s" % w, ImageFont.truetype(HIRA % w, PX, index=0)))
        rows.append(("Friday Sans %s" % style, ImageFont.truetype(
            os.path.join(HERE, "work", "FridaySansCJKProof-%s.ttf" % style), PX)))
    label = ImageFont.truetype(HIRA % "W3", 15, index=0)
    width = PAD * 2 + max(int(f.getlength(t)) for _, f in rows for t in LINES)
    block = 22 + len(LINES) * int(PX * 1.5) + GAP
    img = Image.new("L", (width, PAD * 2 + block * len(rows)), 255)
    d = ImageDraw.Draw(img)
    y = PAD
    for i, (name, font) in enumerate(rows):
        d.text((PAD, y), name, font=label, fill=110)
        yy = y + 22
        for t in LINES:
            d.text((PAD, yy), t, font=font, fill=0)
            yy += int(PX * 1.5)
        y += block
        if i % 2 == 1:
            d.line((PAD, y - GAP // 2, width - PAD, y - GAP // 2), fill=200)
    out = os.path.join(HERE, "previews", "cjk-vs-hiragino.png")
    img.save(out)
    print(out, img.size)

main()
