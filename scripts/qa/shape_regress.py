#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shape the same strings with two builds of a face (HarfBuzz) and compare the result.

    python shape_regress.py --old <dir> --new <dir> [--family FridaySans]

Glyph names, advances and offsets must be equal for every string, every feature set and both
directions that apply.  Expected differences are listed in ALLOWED (U+2252, added in 3.002).
"""
import argparse
import os
import sys
from functools import lru_cache

import uharfbuzz as hb
from fontTools.ttLib import TTFont

ALLOWED = {0x2252}
FEATURE_SETS = [[], ["-kern"], ["+palt"], ["+halt"], ["+fwid"], ["+hwid"], ["+jp78"], ["+jp90"], ["+ss01"],
                ["+ss03"], ["+ss05"], ["+ss07"], ["+cv01"], ["+tnum"], ["+zero"], ["+ruby"], ["-liga", "-calt"],
                ["+case"], ["+vert"], ["+vrt2"], ["+vpal"], ["+vkna"]]
TEXTS = [
    "Hamburgefonstiv 0123456789 AVATAR Wa To Yo fi fl ffi 1/2 1st",
    "The quick brown fox jumps over the lazy dog. @#$%&* ()[]{} -> => != == www",
    "日本語の文章を組むときの文字間隔と約物の処理。「かっこ」（全角）・ｶﾀｶﾅ。",
    "ひらがなカタカナ ぷぶぷ ー〜…‥・、。！？ゞヾ 〱〲",
    "共題武昆廃慮唄圓驀氏祇隄詆壻 国書語園閣鬱麗織難蘭 辻﨑髙 葛󠄀 渡邉",
    "Ⅰ Ⅱ ⑴ ①②③ ㈱ ㌔ ℃ ± × ÷ ≠ ≦ ≧ ∞ ∴ ♂ ♀ ① ㊤ ㈲ ㍿",
    "ÀÉÎÕÜ Ǻ Ấ ẞ ǅ Å ñ ç ø ł Ł Đ đ Ŋ ŋ",
    "αβγ ΑΒΓ абв АБВ ←↑→↓ ■□▲△",
    "A\u0308 a\u0308 o\u0308 u\u0308 e\u0301 n\u0303 a\u0306\u0301 o\u031b\u0301 a\u0323\u0302",
    "か\u3099 は\u309a カ\u3099 ハ\u309a ルビ ruby a\u0308\u0301",
]


@lru_cache(maxsize=20)
def font_and_order(blob_path):
    face = hb.Face(hb.Blob.from_file_path(blob_path))
    font = hb.Font(face)
    with TTFont(blob_path, lazy=True) as tt:
        order = tuple(tt.getGlyphOrder())
    return font, order


def shape(blob_path, text, feats, vertical):
    font, order = font_and_order(blob_path)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    if vertical:
        buf.direction = "ttb"
    hb.shape(font, buf, {f[1:]: (f[0] == "+") for f in feats})
    return [(order[i.codepoint], p.x_advance, p.y_advance, p.x_offset, p.y_offset)
            for i, p in zip(buf.glyph_infos, buf.glyph_positions)]


def same(ro, rn, tol, vertical=False):
    if len(ro) != len(rn):
        return False
    for x, y in zip(ro, rn):
        if x[:4] != y[:4] or abs(x[4] - y[4]) > (tol if vertical else 0):
            return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--family", default="")
    ap.add_argument("--tol", type=int, default=0, help="allowed y_offset difference in vertical shaping only (units): synthesized vertical origins may follow changed outlines without vmtx; advances and horizontal shaping remain exact")
    a = ap.parse_args()
    if a.tol < 0:
        ap.error("--tol must be nonnegative")
    if not os.path.isdir(a.old) or not os.path.isdir(a.new):
        ap.error("--old and --new must be existing directories")
    bad = checked = errors = 0
    def names(directory):
        return {fn for fn in os.listdir(directory) if fn.endswith(".ttf")
                and (not a.family or fn.startswith(a.family + "-"))}
    for fn in sorted(names(a.old) | names(a.new)):
        po, pn = os.path.join(a.old, fn), os.path.join(a.new, fn)
        if not os.path.isfile(po) or not os.path.isfile(pn):
            errors += 1
            print("ERR missing counterpart", fn, po if not os.path.isfile(po) else pn)
            continue
        for text in TEXTS:
            if any(ord(c) in ALLOWED for c in text):
                continue
            for feats in FEATURE_SETS:
                for vertical in (False, True):
                    checked += 1
                    try:
                        ro, rn = shape(po, text, feats, vertical), shape(pn, text, feats, vertical)
                    except Exception as e:
                        errors += 1
                        if errors <= 10:
                            print("ERR", fn, feats, e)
                        continue
                    if not same(ro, rn, a.tol, vertical):
                        bad += 1
                        if bad <= 10:
                            diff = [(x, y) for x, y in zip(ro, rn) if x != y][:2]
                            print("DIFF", fn, feats, "vertical" if vertical else "", text[:20], diff)
    if not checked:
        errors += 1
        print("ERR no shapings checked")
    print("checked %d shapings, %d differ, %d errors" % (checked, bad, errors))
    return 1 if bad or errors else 0


if __name__ == "__main__":
    sys.exit(main())
