#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Friday Mono v48: the sealed v47 faces under their new name.

    python rename_v48.py            # fonts-v47/ -> fonts-v48/

Inori Mono was renamed Friday Mono on 2026-10-01.  Nothing about the design
changed, so v48 is not rebuilt: the v47 faces -- already hinted, audited and
checked on Windows -- are copied and only their `name` table and head
revision are rewritten.  glyf, fpgm, prep, cvt and every layout table stay
byte for byte, which this script asserts, so every v47 rendering result
still holds.

A fresh build from build_inori_v3.py now writes the same names itself.
"""
import glob
import os
import sys

from fontTools.ttLib import TTFont

import build_inori_v3 as build

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "fonts-v47")
OUT = os.path.join(HERE, "fonts-v48")
LICENSE = build.LICENSE           # already the renamed OFL.txt
KEEP = ("glyf", "loca", "fpgm", "prep", "cvt ", "GSUB", "GPOS", "GDEF",
        "cmap", "hmtx", "vmtx", "OS/2", "maxp", "post", "gasp")


def renamed(text):
    for old, new in (("the Inori Mono project authors", "The Friday Project Authors"),
                     ("the Inori Mono project", "The Friday Project"),
                     ("InoriMono", "FridayMono"),
                     ("Inori Mono", "Friday Mono"),
                     ("Reserved Font Name: Inori.", "Reserved Font Name: Friday."),
                     ("Inori", "Friday"),
                     ("Version 4.700", build.VERSION)):
        text = text.replace(old, new)
    return text


def main():
    os.makedirs(OUT, exist_ok=True)
    files = sorted(glob.glob(os.path.join(SRC, "*.ttf")))
    assert len(files) == 12, files
    for path in files:
        font = TTFont(path, recalcTimestamp=False)
        before = {t: font.getTableData(t) for t in KEEP if t in font}
        for rec in font["name"].names:
            text = rec.toUnicode()
            rec.string = LICENSE if rec.nameID == 13 else renamed(text)
        font["head"].fontRevision = build.REVISION
        for rec in font["name"].names:
            assert "Inori" not in rec.toUnicode(), (path, rec.nameID)
        name = renamed(os.path.basename(path))
        dest = os.path.join(OUT, name)
        font.save(dest)
        check = TTFont(dest)
        for tag, data in before.items():
            assert check.getTableData(tag) == data, (name, tag)
        print("  %-34s -> %-36s %s / %s" % (
            os.path.basename(path), name, check["name"].getDebugName(1),
            check["name"].getDebugName(5)))
    print("RENAME OK: %d faces, outlines/hints/layout unchanged" % len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
