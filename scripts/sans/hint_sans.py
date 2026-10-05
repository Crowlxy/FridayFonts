#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hint Friday Sans: ttfautohint for the Latin, then Chlorophytum for the CJK.

    python hint_sans.py                  # fonts/ -> fonts-hinted/
    python hint_sans.py --check          # report on fonts-hinted/ only

Both steps are Friday Mono's own tools, run unchanged: rehint.py (ttfautohint,
plus its digit-row check) and cjkhint.py (Chlorophytum, with the cvt padding
and the program-only transplant that keeps Chrome's OTS happy).

Chlorophytum's CANONICAL_STEM_WIDTH follows the kanji stem.  Regular and
Medium share Friday Mono's stems (64.5, 78.8) and so its configs; Bold's kanji
stem is 100 here against Mono's 113, so it gets inori-sans-Bold.json (0.106,
on the same stem-to-width line as Mono's three).  Caches are per face name,
so FridaySans-* never reads or writes an FridayMono-* cache.

Expect about 45 minutes of Chlorophytum per face on 10 cores the first time.
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MONO = os.path.normpath(os.path.join(HERE, ".."))
PY = os.path.join(MONO, ".venv", "bin", "python")
sys.path.insert(0, MONO)

import cjkhint  # noqa: E402

_mono_weight = cjkhint.weight_of


def weight_of(path):
    weight = _mono_weight(path)
    return "sans-Bold" if weight == "Bold" else weight


cjkhint.weight_of = weight_of


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(HERE, "fonts"))
    ap.add_argument("--out", default=os.path.join(HERE, "fonts-hinted"))
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if not args.check:
        os.makedirs(args.out, exist_ok=True)
        for path in sorted(glob.glob(os.path.join(args.src, "*.ttf"))):
            shutil.copyfile(path, os.path.join(args.out, os.path.basename(path)))
        print("=== ttfautohint ===", flush=True)
        subprocess.run([PY, os.path.join(MONO, "rehint.py"), "--dir", args.out],
                       cwd=MONO, check=True)
    print("=== Chlorophytum ===", flush=True)
    sys.argv = ["cjkhint.py", "--dir", args.out] + (["--check"] if args.check else [])
    return cjkhint.main()


if __name__ == "__main__":
    sys.exit(main())
