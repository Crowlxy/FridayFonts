#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Replace ttfautohint's CJK hints with Chlorophytum ideograph hints.

    python cjkhint.py --dir fonts            # run after rehint.py
    python cjkhint.py --dir fonts --check    # report only, change nothing

ttfautohint has no CJK script, so kana and kanji fall into its "none" style:
no blue zones, and every edge is rounded on its own.  On Windows, where the
TrueType vertical hints are honoured, a voiced kana or a kanji with a high top
stroke then lands one or two pixels above its neighbours, and a single
character looks bigger than the rest of the line.

Chlorophytum (the hinter behind Sarasa Gothic) snaps ideographs and kana to a
shared em box instead.  It only appends to ttfautohint's fpgm, prep and cvt,
and only rewrites the glyph programs of the CJK glyphs it selects, so the
Latin hints -- including rehint.py's digit fixes -- stay byte for byte.

FreeType caps the twilight zone at 2 * (glyph points + cvt entries) to guard
against runaway bytecode.  Chlorophytum puts its em-box points after
ttfautohint's twilight points, well past that cap for a small cvt, and FreeType
then flattens every hinted ideograph to a line.  The cvt is padded with unused
zero entries so the cap never bites.

Analysis takes about 45 minutes per outline set on 10 cores.  Results are cached
in chlorophytum/cache, keyed by face; Plain faces share the cache of their
Mono counterpart because their CJK outlines are identical, and an
unchanged outline is never analysed twice.
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys

from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
# The analysis cache and node_modules live in the research workspace; point
# FRIDAY_CHLOROPHYTUM there (or run `npm ci --prefix chlorophytum` here).
TOOL = os.environ.get("FRIDAY_CHLOROPHYTUM") or os.path.join(HERE, "chlorophytum")
CACHE = os.path.join(TOOL, "cache")
CHECK_SIZES = (12, 16, 20)


def weight_of(path):
    name = os.path.basename(path)
    # SemiBold before Bold: "-SemiBold" does not contain "-Bold", but test the
    # longer names first so a later rename cannot make one swallow the other.
    for weight in ("SemiBold", "Light", "Medium", "Bold"):
        if "-" + weight in name:
            return weight
    return "Regular"


def cache_key(path):
    return os.path.splitext(os.path.basename(path))[0].replace("MonoPlain", "Mono")


def is_cjk(cp):
    return (0x2E80 <= cp <= 0x2FDF or 0x3040 <= cp <= 0x30FF or 0x31C0 <= cp <= 0x31FF
            or 0x3400 <= cp <= 0x9FFF or 0xF900 <= cp <= 0xFAFF or 0x20000 <= cp <= 0x3FFFF)


def already_hinted(font):
    return len(font["cvt "].values) >= font["maxp"].maxTwilightPoints + 4


def chlorophytum(*args):
    subprocess.run(["npx", "--no-install", "chlorophytum", *args], cwd=TOOL, check=True)


def transplant(path, instructed):
    """Carry Chlorophytum's hints over to the face it was given, and nothing else.

    Chlorophytum writes the whole font back out through ot-builder, which
    re-encodes glyf and sets OVERLAP_SIMPLE on the first point of every contour.
    OTS -- the sanitizer in Chrome and Firefox -- rejects that bit anywhere but
    the first point of a glyph and drops the face, so the instructed font is
    used only as a source of programs.  Outlines, flags and every other table
    stay exactly as the build wrote them.
    """
    font = TTFont(path, recalcTimestamp=False)
    hinted = TTFont(instructed)
    for tag in ("fpgm", "prep", "cvt "):
        font[tag] = hinted[tag]
    for field in ("maxZones", "maxTwilightPoints", "maxStorage", "maxFunctionDefs",
                  "maxInstructionDefs", "maxStackElements", "maxSizeOfInstructions"):
        setattr(font["maxp"], field, getattr(hinted["maxp"], field))
    cvt = font["cvt "].values
    cvt.extend([0] * (font["maxp"].maxTwilightPoints + 4 - len(cvt)))

    glyf, source = font["glyf"], hinted["glyf"]
    for name in font.getGlyphOrder():
        old, new = glyf[name], source[name]
        code = new.program.getBytecode() if hasattr(new, "program") else b""
        if code == (old.program.getBytecode() if hasattr(old, "program") else b""):
            continue
        # Only simple glyphs are rehinted, and only their programs may change.
        assert old.numberOfContours > 0, (name, "instructed a composite or empty glyph")
        assert list(old.coordinates) == list(new.coordinates), (name, "outline moved")
        assert list(old.endPtsOfContours) == list(new.endPtsOfContours), (name, "contours changed")
        old.program = new.program
    hinted.close()
    return font


def hint(path):
    font = TTFont(path)
    if already_hinted(font):
        print("  %-30s already carries CJK hints, skipped" % os.path.basename(path))
        return
    font.close()
    config = os.path.join(TOOL, "%s-%s.json" % (os.environ.get("FRIDAY_CJK_CONFIG", "inori"), weight_of(path)))
    cache = os.path.join(CACHE, cache_key(path) + ".gz")
    scratch = os.path.abspath(path) + ".cjkhint"
    hints, out = scratch + ".hint.gz", scratch + ".ttf"
    os.makedirs(CACHE, exist_ok=True)
    try:
        chlorophytum("hint", "-c", config, "-h", cache, "-j", str(os.cpu_count() or 4),
                     os.path.abspath(path), hints)
        chlorophytum("instruct", "-c", config, os.path.abspath(path), hints, out)
        font = transplant(path, out)
        font.save(out)
        shutil.copyfile(out, path)
    finally:
        for scratch_file in (hints, out):
            if os.path.exists(scratch_file):
                os.remove(scratch_file)


def report(path):
    """Every CJK glyph must still render at a plausible height through the hints."""
    from PIL import ImageFont

    font = TTFont(path)
    name = os.path.basename(path)
    if not already_hinted(font):
        print("  %-30s no CJK hints (cvt %d < twilight %d + 4)"
              % (name, len(font["cvt "].values), font["maxp"].maxTwilightPoints))
        return False
    glyf = font["glyf"]
    overlap = [n for n in font.getGlyphOrder()
               if glyf[n].numberOfContours > 0 and any(f & 0x40 for f in glyf[n].flags[1:])]
    if overlap:
        print("  %-30s OVERLAP_SIMPLE past the first point, OTS rejects: %s"
              % (name, overlap[:8]))
        return False
    chars = [(cp, glyf[g]) for cp, g in font.getBestCmap().items()
             if is_cjk(cp) and glyf[g].numberOfContours > 0]
    flat = []
    for px in CHECK_SIZES:
        face = ImageFont.truetype(path, px)
        for cp, glyph in chars:
            box = face.getmask(chr(cp)).getbbox()
            design = (glyph.yMax - glyph.yMin) * px / font["head"].unitsPerEm
            if design >= 2 and (box is None or box[3] - box[1] < design * 0.5):
                flat.append((px, chr(cp)))
    if flat:
        print("  %-30s %d flattened CJK rasters, e.g. %s" % (name, len(flat), flat[:8]))
        return False
    print("  %-30s %d CJK glyphs render at full height" % (name, len(chars)))
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="fonts")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.dir, "*.ttf")))
    if not files:
        print("no fonts in %s" % args.dir)
        return 1
    if not args.check:
        for path in files:
            hint(path)
    ok = all([report(p) for p in files])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
