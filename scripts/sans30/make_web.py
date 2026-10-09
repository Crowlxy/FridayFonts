#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WOFF2 for Friday Sans 3.0: full (all glyphs) and lite (JIS X 0208 + Latin, for the web).

    python make_web.py --ttf <3.0 ttf dir> --out <web dir>

The lite subset keeps every OpenType feature and only drops glyphs outside JIS X 0208,
Latin, general punctuation, kana, full/half-width forms and symbols.
"""
import argparse
import glob
import os
from multiprocessing import Pool

from fontTools import subset
from fontTools.ttLib import TTFont


def jis0208():
    cps = set()
    for lead in range(0x81, 0xEF):
        for trail in range(0x40, 0xFD):
            try:
                ch = bytes([lead, trail]).decode("shift_jis")
            except UnicodeDecodeError:
                continue
            if len(ch) == 1:
                cps.add(ord(ch))
    return cps


def lite_codepoints():
    cps = jis0208()
    for lo, hi in ((0x20, 0x7E), (0xA0, 0x24F), (0x2000, 0x206F), (0x2100, 0x21FF), (0x2200, 0x22FF),
                   (0x2460, 0x24FF), (0x2500, 0x25FF), (0x3000, 0x30FF), (0x31F0, 0x31FF),
                   (0x3200, 0x32FF), (0xFE30, 0xFE4F), (0xFF00, 0xFFEF), (0x1D7CE, 0x1D7FF)):
        cps.update(range(lo, hi + 1))
    return cps


def job(a):
    path, out, lite = a
    base = os.path.basename(path)[:-4]
    f = TTFont(path)
    if lite:
        opts = subset.Options()
        opts.layout_features = ["*"]
        opts.glyph_names = False
        opts.notdef_outline = True
        opts.name_IDs = ["*"]
        opts.name_languages = ["*"]
        opts.legacy_kern = True
        opts.hinting = False
        opts.drop_tables = []
        opts.recalc_bounds = True
        sub = subset.Subsetter(opts)
        sub.populate(unicodes=sorted(lite_codepoints()))
        sub.subset(f)
        dst = os.path.join(out, "lite", base + ".woff2")
    else:
        dst = os.path.join(out, base + ".woff2")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    f.flavor = "woff2"
    f.save(dst)
    return os.path.basename(dst), lite, os.path.getsize(dst), TTFont(dst)["maxp"].numGlyphs


def css(fams, lite):
    sub = "lite/" if lite else ""
    lines = []
    for fam, pre in fams:
        for w, wn in ((300, "Light"), (400, "Regular"), (500, "Medium"), (600, "SemiBold"), (700, "Bold")):
            lines.append('@font-face{font-family:"%s";src:url("%s%s-%s.woff2") format("woff2");'
                         'font-weight:%d;font-style:normal;font-display:swap;}' % (fam, sub, pre, wn, w))
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ttf", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    paths = sorted(glob.glob(os.path.join(a.ttf, "*.ttf")))
    jobs = [(p, a.out, lite) for lite in (False, True) for p in paths]
    with Pool(10) as pool:
        for r in pool.imap_unordered(job, jobs):
            print("%-34s %-5s %8.0f KB %6d glyphs" % (r[0], "lite" if r[1] else "full", r[2] / 1024, r[3]))
    fams = (("Friday Sans", "FridaySans"), ("Friday Sans UI", "FridaySansUI"))
    with open(os.path.join(a.out, "friday-sans.css"), "w", encoding="utf-8") as fh:
        fh.write(css(fams, False))
    with open(os.path.join(a.out, "friday-sans-lite.css"), "w", encoding="utf-8") as fh:
        fh.write(css(fams, True).replace('url("lite/', 'url("lite/'))


if __name__ == "__main__":
    main()
