#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Re-hint the built faces with ttfautohint.

    python rehint.py --dir fonts
    python rehint.py --dir fonts --check    # report only, change nothing

The outlines are rebuilt from scratch by `build_inori_v3.py`, so the faces
carry no TrueType hints at all.  Unhinted, the round digits keep their
overshoot: at 13 px the top of `0` lands on a different pixel row from the top
of `1`, and a column of numbers stops being a column.  It shows up first at
Black, where the overshoot is largest in absolute units.

ttfautohint fixes this the way it fixes it everywhere -- by snapping the digit
height to a blue zone in its own `prep` program at run time.  Hand-written
hints cannot reproduce that, and it leaves the outlines untouched.

`--no-info` is deliberate: the version string is set by the build, and letting
ttfautohint append its own would make the same source produce two different
name tables depending on whether this step ran.
"""
import argparse
import collections
import glob
import os
import shutil
import sys

from fontTools.ttLib import TTFont
from ttfautohint import ttfautohint

SIZES = (9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 24)
DIGITS = "0123456789"


def digit_rows(path):
    """Ink top/bottom of every digit at every size, in device pixels."""
    from PIL import Image, ImageDraw, ImageFont

    bad = {}
    for px in SIZES:
        face = ImageFont.truetype(path, px)
        seen = {}
        for ch in DIGITS:
            img = Image.new("L", (px * 4, px * 4), 0)
            ImageDraw.Draw(img).text((px, px * 3), ch, font=face, fill=255, anchor="ls")
            box = img.getbbox()
            seen[ch] = (box[1], box[3]) if box else None
        if len(set(seen.values())) != 1:
            odd = {c: v for c, v in seen.items()
                   if list(seen.values()).count(v) < len(DIGITS) / 2}
            bad[px] = odd or seen
    return bad


def digit_boxes(path, px):
    """Return the rendered ink box of each digit at one device size."""
    from PIL import Image, ImageDraw, ImageFont

    face = ImageFont.truetype(path, px)
    seen = {}
    for ch in DIGITS:
        img = Image.new("L", (px * 4, px * 4), 0)
        ImageDraw.Draw(img).text((px, px * 3), ch, font=face,
                                 fill=255, anchor="ls")
        box = img.getbbox()
        seen[ch] = (box[1], box[3]) if box else None
    return seen


def number_ranges(values):
    """ttfautohint control-file syntax for a sorted set of integers."""
    values = sorted(set(values))
    groups = []
    start = prev = values[0]
    for value in values[1:]:
        if value == prev + 1:
            prev = value
            continue
        groups.append(str(start) if start == prev else "%d-%d" % (start, prev))
        start = prev = value
    groups.append(str(start) if start == prev else "%d-%d" % (start, prev))
    return ",".join(groups)


def two_top_control(source, hinted, bad):
    """Return a control line when only `2` rises one pixel too early.

    Geist and SF Mono both draw the top of `2` with a real overshoot.  At some
    combinations of width and weight, ttfautohint rounds that curve one pixel
    above the other digits.  A ppem delta keeps the outline and its overshoot
    intact; flattening the curve in font units would not.
    """
    ppems = []
    for px, odd in sorted(bad.items()):
        if set(odd) != {"2"}:
            return None
        boxes = digit_boxes(hinted, px)
        common = collections.Counter(boxes.values()).most_common(1)[0][0]
        two = boxes["2"]
        if not two or not common or two[0] != common[0] - 1 or two[1] != common[1]:
            return None
        ppems.append(px)

    font = TTFont(source, lazy=False)
    name = font.getBestCmap().get(ord("2"))
    glyph = font["glyf"][name] if name else None
    if glyph is None or glyph.isComposite():
        font.close()
        return None
    coords, _, _ = glyph.getCoordinates(font["glyf"])
    top = max(y for _, y in coords)
    points = [i for i, (_, y) in enumerate(coords) if y >= top - 1]
    font.close()
    if not points:
        return None
    return "%s touch %s yshift -1 @ %s\n" % (
        name, number_ranges(points), number_ranges(ppems))


def report(path):
    bad = digit_rows(path)
    name = os.path.basename(path)
    if not bad:
        print("  %-30s digits aligned at every size" % name)
        return True
    print("  %-30s misaligned at %s px" % (name, sorted(bad)))
    for px in sorted(bad)[:2]:
        print("       %d px: %s" % (px, bad[px]))
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="fonts")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.dir, "*.ttf")))
    if not files:
        print("no fonts in %s" % args.dir)
        return 1

    if args.check:
        ok = all([report(p) for p in files])
        return 0 if ok else 1

    failed = []
    for path in files:
        before = digit_rows(path)
        options = dict(
            hinting_range_min=8, hinting_range_max=50, hinting_limit=200,
            increase_x_height=0,        # the x-height is already where we put it
            windows_compatibility=True, no_info=True,
            ignore_restrictions=False)
        scratch = path + ".rehint"
        trial = scratch + ".trial.ttf"
        fixed = scratch + ".fixed.ttf"
        control_path = scratch + ".control.txt"
        try:
            ttfautohint(in_file=path, out_file=trial, **options)
            trial_bad = digit_rows(trial)
            control = two_top_control(path, trial, trial_bad) if trial_bad else None
            chosen = trial
            if control:
                with open(control_path, "w", encoding="ascii") as stream:
                    stream.write(control)
                ttfautohint(in_file=path, out_file=fixed,
                            control_file=control_path, **options)
                chosen = fixed
            shutil.copyfile(chosen, path)
        finally:
            for scratch_file in (trial, fixed, control_path):
                if os.path.exists(scratch_file):
                    os.remove(scratch_file)
        after = digit_rows(path)
        state = "OK" if not after else "still off at %s px" % sorted(after)
        print("  %-30s %2d -> %2d misaligned sizes   %s"
              % (os.path.basename(path), len(before), len(after), state))
        if after:
            failed.append(os.path.basename(path))
    if failed:
        print("\nstill misaligned: %s" % failed)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
