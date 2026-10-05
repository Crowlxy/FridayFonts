#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build Friday Mono (formerly Inori Mono) v3.

    python build_inori_v3.py --out fonts               # all six faces
    python build_inori_v3.py --out fonts --only Regular

Latin outlines come from Iosevka Custom (OFL 1.1), CJK from Noto Sans CJK JP
(OFL 1.1).  SF Mono and Hiragino Kaku Gothic are measured but never copied:
every number taken from them appears in this file as a literal, and no outline
of theirs reaches the output.  See DESIGN.md for where each number came from
and why.

The build never trusts a stem width it has not measured.  Source weights are
solved by bisection against the real outlines, and whatever the solver cannot
reach exactly is made up with an explicit dilation, so a face either hits its
target or says why it did not.
"""
import argparse
import hashlib
import json
import math
import os
import statistics
import sys
import time
import unicodedata

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))

from fontTools.fontBuilder import FontBuilder
from fontTools.misc.transform import Transform
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
import pathops

import shapes

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "Source"))
IOSEVKA = os.path.join(SRC, "Iosevka", "IosevkaCustom-%s.ttf")
IOSEVKA_UNSLASHED = os.path.join(
    SRC, "Iosevka", "IosevkaCustomUnslashed-%s.ttf")
# Light and SemiBold have no npm-built Iosevka static; derive_iosevka_weights.py
# offsets the nearest shipped master to SF Mono's stem and writes them to
# Source/Iosevka/derived.


class _IosevkaPath(str):
    """`IOSEVKA % style` that resolves derived weights to Source/Iosevka/derived."""

    def __new__(cls, stem):
        return str.__new__(cls, os.path.join(SRC, "Iosevka", stem + "-%s.ttf"))

    def __mod__(self, style):
        derived = style.startswith(("Light", "SemiBold"))
        folder = os.path.join(SRC, "Iosevka", "derived") if derived else os.path.join(SRC, "Iosevka")
        return os.path.join(folder, os.path.basename(str.__str__(self)) % style)


IOSEVKA = _IosevkaPath("IosevkaCustom")
IOSEVKA_UNSLASHED = _IosevkaPath("IosevkaCustomUnslashed")
NOTO_CJK = os.path.join(SRC, "noto-cjk", "NotoSansCJKjp-VF.ttf")

# Iosevka's italic is a real italic master, not a slant of the upright: the
# single-storey `a`, the descending `f` and the cursive `k` are drawn, not
# derived.  Both zero plans carry one, so the alternate zero has an italic too.
ITALIC_ANGLE = -10.0     # SF Mono's own slope


def _italic_style(style):
    """Iosevka names the Regular italic `Italic`, the others `<Weight>Italic`."""
    return "Italic" if style == "Regular" else style + "Italic"


UPEM = 1000
LATIN_ADV = 600          # two Latin cells to one CJK cell
CJK_ADV = 1200

# An advance width has no relationship to the em.  A 1000-upem face can
# advance 618 and 1236 and still be a two-to-one grid, so the Latin cell is a
# choice, not a consequence of the em -- an earlier version of this file had it
# backwards and called 500 forced.  600 puts cap/advance at 710/600 = 1.183
# against SF Mono's 1.140; 618 would be 1.149, and is kept as one comparison
# case rather than as the default.
#
# Widening the cell alone would only have bought air: the drawing has to widen
# with it, which is what SF_INK below is for.  --cell overrides the advance
# without touching the drawing, for comparison sheets.
CELL_LATIN = LATIN_ADV
CELL_CJK = CJK_ADV

# Optical size of CJK relative to the Hiragino measurements in section 2.4.
# The frame grows, but the stem solver restores the original weight, and kanji
# and kana share the same multiplier.  1.0 preserves the measured design;
# 1.04 was adopted by real-size visual comparison for the 1200-unit cell.
# The unverified claim that Terminal.app scales a CJK fallback by 1.236 is not
# used as evidence for this value; this is an Inori-specific optical decision.
CJK_SCALE = 1.0

# ---------------------------------------------------------------------------
# Reference measurements.  Numbers only -- see DESIGN.md sections 2 and 4.

# SF Mono, per 1000 upem, H stem and H crossbar.
SF = {
    "Light":   (66.9, 60.5),
    "Regular": (85.4, 79.1),
    "Medium":  (100.6, 90.3),
    "Bold":    (136.2, 119.6),
    "SemiBold": (116.2, 103.0),  # SF Mono Semibold, tools/measure.py
    "Black":   (174.8, 144.0),   # SF Mono Heavy
}
SF_CELL = 618.2
SF_CAP = 704.6
SF_ASCENDER = 738.0      # top of SF Mono's 'l', 33 units above its cap

# SF Mono's `H` ink width over its advance, per weight.  SF does not hold this
# constant: it opens the letter as the face gets heavier so the counters
# survive, from 0.738 at Light to 0.856 at Heavy.  Reference only -- the widths
# below are set relative to v3.1's own drawing, not to these.
SF_INK = {
    "Light":   0.7378,
    "Regular": 0.7583,
    "Medium":  0.7741,
    "Bold":    0.8136,
    "SemiBold": 0.7915,
    "Black":   0.8562,
}

# SF Mono's stems are measured in its own 618.2-unit cell.  Drawing the same
# letter in a narrower cell packs the same ink into less width, so the stems
# are thinned by the square root of the cell ratio to hold the density
# (section 4.2).  v3.1 froze this at the 500-cell value, 0.8993, and kept it
# through the move to 600: the Latin then came out 11 % lighter than SF while
# the CJK -- whose target divides the correction back out -- did not, so the
# 0.755 Latin-to-CJK stem pairing the whole family rests on measured 0.855 and
# the face read thin on screen.  Derive it from the cell actually drawn in.
STEM_CORRECTION = (LATIN_ADV / SF_CELL) ** 0.5

# A contour smaller than this, and under two percent of the glyph it sits in,
# is a solver hair rather than a mark.  The floor is set by the smallest real
# thing the font draws: a hiragana dakuten measures about 6,600 square units,
# a katakana one 6,600, the counter of 国 6,700.  The largest hair measured
# 1,484.  4,000 sits between them with room on both sides.
SPUR_AREA = 4000.0

# How far a finished CJK glyph's ink may sit from the ink the whole font moved
# by, before it is treated as damage and the scaled source is kept instead.
# The healthy 99.6 % of the repertoire lands inside 10 %; every glyph outside
# 15 % was visibly broken.
INK_TOLERANCE = 0.12

# How much of its own shape a finished glyph must still share with the source,
# measured as overlap once both are normalised to their own ink.  The healthy
# repertoire sits at 0.86 and its worst honest case at 0.65; the two glyphs
# that were actually destroyed measured 0.34, 0.56 and 0.64.  The floor stops
# short of 0.70, where し and じ sit: a kana of two strokes shares a smaller
# fraction of its pixels after any weight change at all, and reverting those
# would hand back the very kana the bar-correction guard just repaired.
# Measured over 1,500 kanji of a finished Regular whose ink outliers had
# already been dealt with, the honest distribution bottoms out at 0.69, so
# 0.68 sits just under it.  The margin is thin, and it is meant to be: by the
# time a glyph reaches this test the contour count and the ink have both
# passed, and what is left to catch is gross.
SHAPE_FLOOR = 0.68
# How far above its own population an 8x8 tile of a 64-pixel raster may be
# fuller than the source before the glyph is called damaged, in multiples of
# the spread from the median to the ninth decile.  Five puts Regular's ceiling
# at 0.25 (median 0.016, p90 0.062), which catches 和 0.33 and 按 0.41 -- both
# really are marked -- and Bold's at 0.56 (median 0.172, p90 0.25), which
# leaves 孯 0.50 alone, correctly: at Bold the correction is a dilation and
# every glyph in the face gains ink.
EXCESS_SPREADS = 5.0
#: Hard ceiling on local surplus, whatever the face's own distribution says.
#: `EXCESS_SPREADS` is a relative outlier test: it takes its centre and its
#: spread from the population being tested, so if a pass damages most of the
#: repertoire the ceiling rises with the damage and the test finds nothing.
#: The largest surplus measured on a *sound* glyph is Bold's 撦 / 鏆 group at
#: 0.38-0.50; the smallest on a destroyed one is 談 at 1.00.  0.60 sits
#: between them and does not move.
EXCESS_ABSOLUTE = 0.60

#: Fractions of a correction `settle_largest` will try, largest first.  See
#: that function for why this is a descending scan and not a bisection.
SETTLE_LADDER = (1.0, 0.875, 0.75, 0.625, 0.5, 0.375, 0.25, 0.125)

# Iosevka is drawn in the final 600-unit cell.  Keep its horizontal scale at
# one unless --widen is explicitly used for an experiment.
#
#   widen   字面/送り at 600     at 618
#   1.00        0.667            0.647
#   1.08        0.720            0.699
#   1.10        0.733            0.712
#   1.12        0.747            0.725
#   1.14        0.760            0.738     (SF Mono is 0.758)
# Gen Jyuu draws some one-column symbols full-width (the star is 970 units of
# ink).  When such a glyph is moved into the half-width cell it is scaled down
# uniformly until its ink fits this share of the cell.
HALFWIDTH_FIT = 0.92

LATIN_WIDEN = 1.0
LATIN_XS = LATIN_WIDEN

# SF Mono does not give every letter the same share of its cell.  The ink width
# of each glyph over the ink width of the same face's `H` is the face's width
# rhythm, and it is not Geist's: SF draws `a` and `s` at 0.887 of `H` where
# Geist draws them at 1.03 and 0.92, and it opens `n` `u` `r` where Geist
# closes them.  The rhythm also moves with weight -- `a` `n` `u` `h` `k` `x`
# `0` `2` `6` `8` `9` all widen as the face gets heavier, which is how SF keeps
# their counters open instead of letting the stems eat them.  Geist holds them
# nearly flat.  Both halves of that are transplanted in `build_latin`.
#
# Rows are Light / Regular / Medium / Bold / Black (SF Mono Heavy for Black),
# measured with tools/measure_open.py widths.  Ratios, not units, so they carry
# over to our narrower cell untouched.
SF_WIDTH = {
    "a": (0.875, 0.887, 0.897, 0.918, 0.938),
    "b": (0.957, 0.965, 0.971, 0.983, 0.996),
    "c": (0.929, 0.936, 0.943, 0.953, 0.964),
    "d": (0.957, 0.965, 0.971, 0.984, 0.996),
    "e": (0.942, 0.945, 0.947, 0.950, 0.957),
    "f": (0.976, 0.977, 0.978, 0.978, 0.977),
    "g": (0.957, 0.969, 0.979, 0.997, 1.016),
    "h": (0.912, 0.927, 0.939, 0.962, 0.986),
    "i": (0.943, 0.936, 0.934, 0.925, 0.917),
    "j": (0.767, 0.761, 0.757, 0.749, 0.739),
    "k": (0.905, 0.929, 0.947, 0.985, 1.025),
    "l": (0.943, 0.936, 0.934, 0.925, 0.917),
    "m": (1.092, 1.090, 1.088, 1.082, 1.076),
    "n": (0.912, 0.925, 0.935, 0.953, 0.974),
    "o": (0.976, 0.979, 0.982, 0.984, 0.989),
    "p": (0.957, 0.965, 0.971, 0.983, 0.996),
    "q": (0.957, 0.965, 0.971, 0.983, 0.996),
    "r": (0.998, 1.008, 1.015, 1.032, 1.048),
    "s": (0.876, 0.887, 0.896, 0.913, 0.930),
    "t": (0.934, 0.934, 0.936, 0.938, 0.940),
    "u": (0.912, 0.925, 0.935, 0.953, 0.974),
    "v": (1.011, 1.021, 1.031, 1.047, 1.065),
    "w": (1.233, 1.221, 1.212, 1.190, 1.168),
    "x": (0.973, 0.988, 0.999, 1.023, 1.046),
    "y": (1.012, 1.027, 1.040, 1.065, 1.090),
    "z": (0.876, 0.879, 0.882, 0.887, 0.891),
    "A": (1.163, 1.165, 1.165, 1.167, 1.168),
    "B": (1.003, 1.006, 1.009, 1.014, 1.018),
    "C": (1.080, 1.077, 1.073, 1.067, 1.061),
    "D": (1.069, 1.061, 1.058, 1.047, 1.036),
    "E": (0.889, 0.887, 0.886, 0.883, 0.880),
    "F": (0.888, 0.886, 0.888, 0.885, 0.884),
    "G": (1.079, 1.073, 1.069, 1.061, 1.052),
    "H": (1.000, 1.000, 1.000, 1.000, 1.000),
    "I": (0.767, 0.792, 0.812, 0.856, 0.899),
    "J": (0.868, 0.890, 0.906, 0.942, 0.977),
    "K": (1.062, 1.071, 1.077, 1.089, 1.101),
    "L": (0.898, 0.895, 0.893, 0.886, 0.880),
    "M": (1.099, 1.083, 1.073, 1.050, 1.026),
    "N": (1.009, 1.000, 0.996, 0.983, 0.969),
    "O": (1.111, 1.102, 1.094, 1.078, 1.061),
    "P": (0.979, 0.982, 0.988, 0.993, 1.001),
    "Q": (1.122, 1.107, 1.095, 1.078, 1.061),
    "R": (1.007, 1.015, 1.020, 1.032, 1.043),
    "S": (1.045, 1.047, 1.049, 1.051, 1.054),
    "T": (1.096, 1.092, 1.088, 1.078, 1.068),
    "U": (1.066, 1.058, 1.055, 1.043, 1.030),
    "V": (1.163, 1.165, 1.165, 1.167, 1.168),
    "W": (1.355, 1.319, 1.292, 1.229, 1.168),
    "X": (1.171, 1.171, 1.171, 1.169, 1.168),
    "Y": (1.191, 1.185, 1.184, 1.175, 1.168),
    "Z": (1.054, 1.035, 1.023, 0.994, 0.965),
    "0": (0.998, 1.015, 1.027, 1.053, 1.079),
    "1": (1.069, 1.051, 1.038, 1.007, 0.977),
    "2": (0.942, 0.959, 0.973, 1.003, 1.031),
    "3": (1.022, 1.031, 1.039, 1.052, 1.066),
    "4": (1.088, 1.083, 1.080, 1.071, 1.062),
    "5": (0.999, 1.006, 1.012, 1.024, 1.036),
    "6": (1.005, 1.022, 1.036, 1.063, 1.090),
    "7": (1.006, 1.003, 1.002, 0.996, 0.991),
    "8": (1.041, 1.059, 1.073, 1.104, 1.135),
    "9": (1.005, 1.022, 1.035, 1.063, 1.090),
}

# How much of its cell the design may reshape.  Past ten percent the letter
# stops being the letter that was drawn: SF's `W` is 17 % wider than Geist's
# relative to `H`, and squeezing Geist's into that would be a different W, not
# a better one.  The clamp is reported per face so the shortfall is visible.
WIDTH_CLAMP = 0.10

# Set by --kana-uniform.  See build_cjk.
WIDTH_DEADBAND = 0.02   # below this the change is not worth the outline surgery


# Hiragino Kaku Gothic W0-W9, every figure taken with this build's own
# measuring code (tools/measure_open.py and the ladder script reproduce them).
# Mixing metrics is what went wrong first: 字面 has to be read on characters
# that fill the em square, but the *stem* anchor that the whole Latin-to-CJK
# ratio rests on was measured on the ten-character sample and validated against
# W3/W4/W6 there, so the two samples are kept apart and each number says which
# it came from.
#
# Kanji stem, median over 日国書語東目田口回目 -- the anchor, unchanged.
HIRAGINO_W3_KANJI_STEM = 64.5

# Everything else is the *ladder itself*: one value per weight, read off at the
# face's own CJK stem by interpolating between them.
#
# v3.1 and v3.2 fitted a straight line through W3 and W6 and extrapolated.
# That is fine inside the range and wrong outside it, and two of the five
# weights are outside it.  Hiragino's kana ratios are not monotone -- the
# katakana stem ratio peaks at W6 (1.242) and comes back down to 1.208 at W9 --
# so the line asked Black for 1.265, a value the family never reaches at any
# weight.  Reading the ladder and clamping at its ends cannot invent a target
# that Hiragino does not have.
HIRAGINO_STEMS = (22.0, 43.0, 52.5, 64.5, 77.5, 91.0, 109.5, 130.5, 152.5, 180.5)

# 字面, median over the fifteen full-frame characters.  v3.0 read this off the
# ten-character sample too, half of which (日目田口回) is narrow by design, and
# the mixed median of widths and heights it produced said Zen Kaku was 5.8 %
# smaller than Hiragino where on full-frame characters the two are the same
# size to within 0.2 %.  The face shipped 5.7 % too large.
HIRAGINO_FRAME_W = (887.0, 893.0, 897.0, 902.0, 908.0, 914.0, 922.0, 931.0, 941.0, 953.0)
HIRAGINO_FRAME_H = (870.0, 882.0, 886.0, 891.0, 897.0, 903.0, 911.0, 922.0, 933.0, 945.0)
HIRAGINO_FRAME_C = (367.0, 369.0, 368.5, 368.5, 368.5, 369.0, 370.5, 371.5, 372.5, 375.5)

# Horizontal over vertical, as the median of each glyph's own ratio -- which is
# how the correction is applied, one glyph at a time, so it is how the target
# has to be read.  v3.0 divided a median bar by a median stem taken over a
# different set of characters and got 0.946 for the same quantity; the two
# aggregations disagree by five percent and mixing them is what left the
# horizontals visibly off.
HIRAGINO_BAR_OVER_STEM = (0.9091, 0.8793, 0.8909, 0.8923, 0.9037, 0.9040, 0.9005, 0.9043, 0.8951, 0.8994)

# Kana against the kanji.  Zen Kaku draws them narrower than Hiragino and sits
# them a shade below the kanji centre; Hiragino lifts both classes above it,
# the hiragana by twelve units at W3 and the katakana by nine.  Width, height
# and height-above-centre are three separate numbers in Hiragino and are
# treated as three here.  Ratios are against the *frame* sample, stems against
# the kanji stem, over all 46 basic hiragana and all 46 basic katakana.
HIRAGINO_HIRA_STEM = (1.0535, 1.1056, 1.1271, 1.1399, 1.1450, 1.1542, 1.1516, 1.1462, 1.1477, 1.1234)
HIRAGINO_KATA_STEM = (1.1110, 1.1957, 1.2232, 1.1898, 1.2252, 1.2334, 1.2540, 1.2335, 1.2492, 1.1967)

# The kana's own horizontal-over-vertical, which is not the kanji's: Hiragino
# runs its hiragana at 0.927 and its katakana at 0.897 against 0.892 for kanji.
#
# Zen Kaku's katakana already sit at 0.898, so the source was right and v3.1
# broke it: stretching a katakana 12 % taller to reach Hiragino's proportions
# stretches its horizontal strokes with it, and nothing took that back out.
# Measured against Hiragino the katakana came out at 0.930 -- the reading-heavy
# katakana this fixes.
HIRAGINO_HIRA_BAR = (0.9582, 0.9312, 0.9411, 0.9266, 0.9315, 0.9268, 0.9102, 0.9205, 0.9151, 0.9040)
HIRAGINO_KATA_BAR = (0.9410, 0.8776, 0.8833, 0.8965, 0.8943, 0.8855, 0.8737, 0.8877, 0.8709, 0.8749)

HIRAGINO_HIRA_W = (0.8602, 0.8656, 0.8735, 0.8836, 0.8921, 0.9004, 0.9127, 0.9253, 0.9400, 0.9580)
HIRAGINO_HIRA_H = (0.9098, 0.9031, 0.9108, 0.9175, 0.9220, 0.9308, 0.9402, 0.9512, 0.9609, 0.9725)
HIRAGINO_HIRA_RISE = (17.0, 15.0, 15.0, 12.0, 14.0, 15.0, 14.0, 8.2, 5.8, 6.5)
HIRAGINO_KATA_W = (0.8315, 0.8410, 0.8495, 0.8598, 0.8700, 0.8813, 0.8964, 0.9103, 0.9187, 0.9355)
HIRAGINO_KATA_H = (0.8609, 0.8588, 0.8657, 0.8743, 0.8824, 0.8931, 0.9050, 0.9197, 0.9373, 0.9508)
HIRAGINO_KATA_RISE = (10.8, 9.0, 9.5, 9.2, 7.8, 7.5, 5.2, 2.5, 0.5, -0.2)

# How heavy a dense character is against a simple one.  Hiragino holds this
# near 0.84 from W1 to W9 -- one of the most stable numbers in the family --
# while Zen Kaku lets it drift from 0.880 at Regular to 0.803 at Black.
#
# v3.1 corrected every kanji by the same *absolute* number of units, which
# cannot preserve any such ratio: adding 19 units to a 100-unit stem and to an
# 85-unit one gives 119 and 104, and the ratio climbs from 0.85 toward 1.
# Inori Bold measured 0.877 where Hiragino W6 is 0.846, and dense characters
# were the first thing to go muddy.  v3.2 measures each glyph and corrects it
# by a proportion, then remaps the spread onto Hiragino's.
#
# W0 is a copy of W1: at a 22-unit stem every character rounds to the same
# integer and the ratio reads exactly 1.000, which is the measurement failing,
# not the design.
HIRAGINO_DENSE_OVER_SIMPLE = (0.8864, 0.8864, 0.8624, 0.8436, 0.8491, 0.8421, 0.8456, 0.8338, 0.8222, 0.8271)

# Characters that fill the frame with few strokes, and characters that fill it
# with many.  The two medians are what the remap above is anchored on.
SIMPLE_SAMPLE = "一二三十日月木口国目田"
DENSE_SAMPLE = "鬱欝麗織難蘭鑑鷹籠躍驚顕"

# Kana with a clear horizontal and a clear vertical.  `く` and `ノ` have no
# horizontal at all, and `シ` `ス` `ツ` are diagonals whose horizontal span is
# their thickness divided by the sine of their angle -- 240 units where `ア`
# reads 167.  Both the stem and the bar of the kana are measured here, so the
# ratio between them is taken on the same characters it is applied to; the
# stem ladders above are measured on this sample too.
HIRA_BAR_SAMPLE = "あえおかきさしすせたなにぬねひふほまみむらりるろわを"
KATA_BAR_SAMPLE = "アエオカキサシスセタナニヌネヒフホマミムラリルロワヲ"
KANJI_BAR_SAMPLE = "日国書語東目田口回国安京花時明線黒番"


def _at(ladder, stem):
    """Read a Hiragino quantity off the W0-W9 ladder at an arbitrary stem.

    Linear between the two weights that bracket it, held flat outside the ends.
    The alternative -- a straight line fitted to two weights -- reported values
    at Light and Black that Hiragino does not have at any weight.
    """
    xs = HIRAGINO_STEMS
    if stem <= xs[0]:
        return ladder[0]
    if stem >= xs[-1]:
        return ladder[-1]
    for i in range(len(xs) - 1):
        if xs[i] <= stem <= xs[i + 1]:
            t = (stem - xs[i]) / (xs[i + 1] - xs[i])
            return ladder[i] + (ladder[i + 1] - ladder[i]) * t
    return ladder[-1]


# Japanese stems run thinner than the Latin they sit beside, and the gap
# narrows as weight rises.  Anchor: SF Mono Regular (85.4) pairs with Hiragino
# W3 (64.5) in macOS itself, giving 0.755.  Slope 0.0013 per unit of CJK stem
# is the mean of Yu Gothic (0.711 -> 0.817) and Meiryo (0.831 -> 0.894), both
# families that draw their own Latin.  Solving J = r(J)*L for J reproduces
# Hiragino W3 / W4 / W6 to within a unit at Regular / Medium / Bold, which is
# the check that this model is not invented.
JP_RATIO_ANCHOR = HIRAGINO_W3_KANJI_STEM / SF["Regular"][0]
JP_RATIO_SLOPE = 0.0013


def jp_stem_target(latin_stem):
    """Solve J = (anchor + slope*(J - J0)) * L for J."""
    j0 = HIRAGINO_W3_KANJI_STEM
    a = JP_RATIO_ANCHOR - JP_RATIO_SLOPE * j0
    return a * latin_stem / (1.0 - JP_RATIO_SLOPE * latin_stem)


# The reference ladders -- SF_WIDTH's width rhythm, SF's stems -- are five
# columns wide and are read by column index, so a style's column must not move
# when a weight is dropped from the shipping family.  The ladder is fixed; the
# family is the subset of it that ships.
# SemiBold came later; it is appended so the five original columns keep their
# indices.  Its SF_WIDTH column is measured from SF Mono Semibold the same way
# (tools/measure_open.py ink width over H), which reproduces the Bold column
# to the third decimal.
SF_WIDTH_SEMIBOLD = {'a': 0.906, 'b': 0.977, 'c': 0.947, 'd': 0.977, 'e': 0.949, 'f': 0.977, 'g': 0.987, 'h': 0.949, 'i': 0.93, 'j': 0.753, 'k': 0.964, 'l': 0.93, 'm': 1.084, 'n': 0.944, 'o': 0.984, 'p': 0.977, 'q': 0.977, 'r': 1.023, 's': 0.902, 't': 0.937, 'u': 0.944, 'v': 1.038, 'w': 1.202, 'x': 1.01, 'y': 1.051, 'z': 0.884, 'A': 1.166, 'B': 1.011, 'C': 1.071, 'D': 1.053, 'E': 0.885, 'F': 0.885, 'G': 1.066, 'H': 1.0, 'I': 0.832, 'J': 0.922, 'K': 1.083, 'L': 0.889, 'M': 1.064, 'N': 0.99, 'O': 1.088, 'P': 0.99, 'Q': 1.088, 'R': 1.026, 'S': 1.05, 'T': 1.084, 'U': 1.048, 'V': 1.166, 'W': 1.263, 'X': 1.17, 'Y': 1.18, 'Z': 1.011, '0': 1.039, '1': 1.024, '2': 0.987, '3': 1.045, '4': 1.076, '5': 1.018, '6': 1.048, '7': 1.0, '8': 1.088, '9': 1.048}
SF_WIDTH = {c: v + (SF_WIDTH_SEMIBOLD[c],) for c, v in SF_WIDTH.items()}
LADDER = ["Light", "Regular", "Medium", "Bold", "Black", "SemiBold"]
STYLES_INDEX = {n: i for i, n in enumerate(LADDER)}

STYLES = [
    # name, os2 weight
    ("Light", 300), ("Regular", 400), ("Medium", 500), ("SemiBold", 600),
    ("Bold", 700),
]

VERSION = "Version 4.800"

#: How much heavier a capital is drawn than the rest of the alphabet.
#: A capital is cap-height tall with open counters, so at the stem of a
#: lowercase it reads lighter than one.  SF Mono draws its capitals 2.9 %
#: heavier -- 85.4 against 83.0 -- rather than equal, and this follows it.
#: `validate.py` reads the same constant: its Latin probe is `H`, which is
#: itself a capital, so the stem and bar it expects there are the design
#: targets times this.
CAP_OPTICAL = 0.030
REVISION = 4.800
FAMILY = "Friday Mono"
VENDOR = "INOR"

COPYRIGHT = (
    "Copyright 2026 The Friday Project Authors. "
    "Copyright 2015-2026, Renzhi Li (aka. Belleve Invis, belleve@typeof.net). "
    "Copyright 2014-2021 Adobe (http://www.adobe.com/), with Reserved Font Name Source. "
    "Derived from Iosevka and Noto Sans CJK JP. Reserved Font Name: Friday."
)
LICENSE = open(os.path.join(HERE, "OFL.txt"), encoding="utf-8").read()
LICENSE_URL = "https://openfontlicense.org"
MANUFACTURER = "The Friday Project"
PROJECT_URL = "https://openfontlicense.org"
SAMPLE_TEXT = "Friday Mono 0123 あア漢 if (x == 0) { return; }"
DESCRIPTION = (
    "A Japanese monospaced coding typeface derived from Iosevka and Noto Sans CJK JP, "
    "with original Friday kana drawings. Latin/CJK advances: 600/1200 at 1000 UPM."
)

# Lowercase ascenders.  SF Mono puts them 33 units above the cap so that l, I
# and 1 differ in silhouette height as well as in width; Geist Mono flattens
# all three to the cap, which erases the distinction at terminal sizes.
ASCENDERS = "bdfhkl" + "ij"

# Codepoints that must come from the CJK source even when the Latin font also
# covers them.  Geist Mono draws a half-width U+3003 and U+301C, which would
# otherwise land in a 500 cell and break the two-Latin-cells-to-one-CJK-cell
# rule that the whole grid rests on.
CJK_FIRST = [(0x2E80, 0x303F), (0x3040, 0x33FF), (0x3400, 0x4DBF),
             (0x4E00, 0x9FFF), (0xF900, 0xFAFF), (0xFE30, 0xFE4F),
             (0xFF00, 0xFF60), (0xFFE0, 0xFFE6)]


def is_cjk_cp(cp):
    return any(lo <= cp <= hi for lo, hi in CJK_FIRST)


#: 自分の形を持つ記号は和文側からもらう。
#:
#: Iosevka は記号を自分の文字の比率で描く ―― `O` も `0` も ① も © も ⚠ も
#: 縦横 1.7 で、書体としては筋が通っている。だが丸数字が丸に見えず、警告標識が
#: 二等辺三角形になり、スペードが縦に伸びる。形そのものが持つ意味が消える。
#: SF Mono は同じ問題を、記号だけ真円にしてセル幅いっぱいに置いて解いている
#: （① 618x611 に対し `O` は 517x734）。
#:
#: ここでは和文側の字形をもらい、半角セルへ等倍で収める。潰すのではなく縮める
#: ので形は保たれる。倍率は他の全角由来の半角記号と同じ HALFWIDTH_FIT。87 字が
#: 移り、縦横比が 0.15 以上動く 45 字はすべて 1.0 に近づく側へ動く。
#:
#: 罫線は入れない。あれは端末の格子を敷き詰めるためのもので、和文側は別の律で
#: 引いている（`│` の縦横比が 16.5 から 25.0 になる）。矢印も入れない ―― `←`
#: は 0.73 から 0.49 へ、正方形から遠ざかる側に動く。
SYMBOLS_FROM_CJK = ((0x2460, 0x24FF),    # 囲み英数字   ① Ⓐ ⓘ
                    (0x1F100, 0x1F1FF),  # 囲み英数字補助 🄰
                    (0x2600, 0x26FF),    # その他の記号  ⚠ ♪ ♠ ☀
                    (0x2700, 0x27BF))    # 装飾記号     ❶ ✿ ✓
#: 上のどのブロックにも入らないが同じ事情の字。`®` は Iosevka のものが既に真円
#: で、和文側は 397 と一回り小さいので触らない。
SYMBOL_SINGLES = (0x25CB, 0x25CF, 0x25CE, 0x25EF, 0x00A9)


def is_symbol_from_cjk(cp):
    return (cp in SYMBOL_SINGLES
            or any(lo <= cp <= hi for lo, hi in SYMBOLS_FROM_CJK))


def is_fullwidth_cp(cp):
    """Two cells or one, decided the way the terminal itself decides it.

    `CJK_FIRST` answers a different question -- which source a codepoint is
    drawn from -- and it stops at U+FFE6.  Using it for the cell as well put
    303 of the ideographs this font ships (CJK Extension B and later, which
    JIS X 0213 encodes and the keep rule therefore admits) into the 600-unit
    cell, where they were scaled down to 552 units of ink against 895 for an
    ordinary kanji.  The terminal still gave them two columns, because the
    terminal asks Unicode, so they drew at half size in half the space they
    were allotted.  The same went for the enclosed CJK squares, the vertical
    punctuation at U+FE10, and the wide symbols.

    So ask Unicode as well, and take the union.  W and F are Unicode's
    two-column classes; `CJK_FIRST` keeps its say because a few characters in
    it are ambiguous to Unicode and unreadable at half width -- ㉈ to ㉏ lose
    62 % of their ink when they are fitted into a 600-unit cell, which the ink
    guard catches.  The union changes 505 characters from one cell to two and
    none the other way, so nothing that reads correctly today stops.

    What the union leaves behind is 〿 (U+303F, neutral to Unicode) and those
    eight circled numbers, all nine of them full-width against a terminal that
    will give them one column.  They were full-width before this too.
    """
    return (unicodedata.east_asian_width(chr(cp)) in ("W", "F")
            or is_cjk_cp(cp))


# What the family ships.  Noto Sans CJK JP carries every script the pan-CJK
# project covers -- 11,172 Hangul syllables and some twenty thousand ideographs
# that no Japanese text encoding has ever addressed -- and carrying them cost
# 50,822 glyphs and 15.7 MB a face.
#
# The keep rule is a Japanese *encoding* rule, not a hand-picked list: an
# ideograph stays if JIS X 0213 or Windows-31J can encode it.  The two are
# asked directly, so there is no character table to import and no table to
# fall out of date.  0213 alone would drop 髙, which cp932 has and which real
# Japanese software emits, so the union is the rule and not either half.
#
# Everything the rule drops falls back to the platform's own Japanese face,
# which is what a coding font should do with a character it was never for.
IDEOGRAPH_BLOCKS = [(0x3400, 0x4DBF), (0x4E00, 0x9FFF),
                    (0xF900, 0xFAFF), (0x20000, 0x3FFFF)]
HANGUL_BLOCKS = [(0x1100, 0x11FF), (0x3130, 0x318F), (0xAC00, 0xD7FF)]
JP_ENCODINGS = ("shift_jis_2004", "cp932")


def _in_blocks(cp, blocks):
    return any(lo <= cp <= hi for lo, hi in blocks)


def ships(cp):
    """True if the family draws this codepoint itself."""
    if _in_blocks(cp, HANGUL_BLOCKS):
        return False
    if not _in_blocks(cp, IDEOGRAPH_BLOCKS):
        return True
    for codec in JP_ENCODINGS:
        try:
            chr(cp).encode(codec)
            return True
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return False


def jp_coverage(cmap):
    """The source character map, cut down to what the family ships."""
    return {cp: name for cp, name in cmap.items() if ships(cp)}


# ---------------------------------------------------------------------------
# 仮名の縦リズム
#
# Inori knows something Hiragino cannot know: every character lands in the same
# 1200-unit cell.  Hiragino is a proportional text face, so the vertical scatter
# of its kana is a virtue there and a defect here -- in a fixed cell the same
# scatter reads as a column of characters bobbing up and down.
#
# Two separate things are being corrected, and only one of them is Hiragino's.
#
# HIRAGINO_KANA_RHYTHM is *which way* each kana should sit: つ, て, へ, ソ, フ
# and マ belong low and と, ち, お and セ belong high, and that judgement is
# thirty years old and not ours to re-derive.  The numbers are the deviation of
# each character's ink centre from its class mean, in 1000-upem units, averaged
# over W3/W5/W6 -- the spread between those weights is 3.2-3.7u against the
# deviation's own 13.3u, so one table serves all three.
#
# KANA_RHYTHM_GAIN is *how far* we go along with it.  At 1.0 the family adopts
# Hiragino's rhythm exactly; below 1.0 it holds the same relative order and
# tightens the whole pattern, which is the move a monospace face is entitled to
# and a text face is not.  0.8 takes the scatter to about 11u against
# Hiragino's own 14u.  Lower flattens the kana toward a mechanical grid; this
# is a taste knob and it is meant to be visible in `--kana-rhythm`.
KANA_RHYTHM_GAIN = 0.8

HIRAGINO_KANA_RHYTHM = {
    "あ": 6.2, "い": -10.8, "う": -1.1, "え": 5.7, "お": 15.2, "か": 8.7,
    "き": 8.4, "く": -2.4, "け": -6.1, "こ": -9.1, "さ": 10.9, "し": 0.1,
    "す": -4.8, "せ": 10.7, "そ": -8.4, "た": 12.2, "ち": 17.4, "つ": -33.9,
    "て": -29.4, "と": 20.1, "な": 9.2, "に": 2.9, "ぬ": 14.1, "ね": 2.7,
    "の": -20.4, "は": 1.7, "ひ": -10.1, "ふ": 3.2, "へ": -24.8, "ほ": 3.1,
    "ま": 7.4, "み": -17.8, "む": 5.4, "め": 4.7, "も": 9.7, "や": -4.6,
    "ゆ": -7.3, "よ": 5.2, "ら": 8.6, "り": 4.7, "る": -8.4, "れ": -0.1,
    "ろ": -7.1, "わ": -0.3, "ゐ": -5.4, "ゑ": -10.1, "を": 13.7, "ん": 9.4,
    "ア": -17.3, "イ": 10.0, "ウ": 12.5, "エ": 9.0, "オ": 5.3, "カ": 17.5,
    "キ": 4.3, "ク": 13.2, "ケ": 10.8, "コ": -15.7, "サ": 3.2, "シ": 8.0,
    "ス": -15.0, "セ": 20.3, "ソ": -28.0, "タ": 11.8, "チ": 3.0, "ツ": -16.5,
    "テ": -15.3, "ト": 10.3, "ナ": 5.5, "ニ": 8.7, "ヌ": -10.3, "ネ": 8.7,
    "ノ": 11.3, "ハ": -1.8, "ヒ": 18.8, "フ": -25.8, "ヘ": -13.2, "ホ": 8.0,
    "マ": -24.8, "ミ": 3.3, "ム": 12.3, "メ": 8.8, "モ": -1.8, "ヤ": 10.3,
    "ユ": 10.7, "ヨ": -9.7, "ラ": -8.2, "リ": -4.8, "ル": 0.3, "レ": 4.7,
    "ロ": -12.7, "ワ": -19.0, "ヰ": 5.3, "ヱ": 10.3, "ヲ": -12.0, "ン": -13.8
}

# The other correction is Noto's alone.  A voiced kana carries its dakuten in
# the top right, and Noto makes room by sitting the body lower: が's body
# bottom is 13.9u under か's, where Hiragino holds the same pair to 4.3u.  In
# running text that is か and が failing to sit on one line.  The fix reads the
# body of each voiced kana -- everything that is not a small mark in the top
# right corner -- and puts its centre where the unvoiced partner's is.
VOICED_BASE = {}
for _voiced, _plain in zip(
        "がぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽゔ",
        "かきくけこさしすせそたちつてとはひふへほはひふへほう"):
    VOICED_BASE[_voiced] = _plain
for _voiced, _plain in zip(
        "ガギグゲゴザジズゼゾダヂヅデドバビブベボパピプペポヴヷヸヹヺ",
        "カキクケコサシスセソタチツテトハヒフヘホハヒフヘホウワヰヱヲ"):
    VOICED_BASE[_voiced] = _plain
del _voiced, _plain

HIRAGANA = range(0x3041, 0x3097)
KATAKANA = list(range(0x30A1, 0x30FB)) + list(range(0xFF66, 0xFFA0))
KANJI_SAMPLE = "日国書語東目田口回目"

# 字面 is what a character does with the whole em square, so it has to be read
# on characters that fill it.  Half of the ten-character sample above is narrow
# by design and reading 字面 off it is what made v3.0 six percent too big.
FRAME_SAMPLE = "国書語園閣鬱麗織難蘭圏題観層盤"
HIRA_SAMPLE_FULL = ("あいうえおかきくけこさしすせそたちつてとなにぬねの"
                    "はひふへほまみむめもやゆよらりるれろわをん")
KATA_SAMPLE_FULL = ("アイウエオカキクケコサシスセソタチツテトナニヌネノ"
                    "ハヒフヘホマミムメモヤユヨラリルレロワヲン")


# ---------------------------------------------------------------------------


def log(msg):
    print(msg, flush=True)


def outlines(font, glyphset=None):
    """name -> recording, with every composite decomposed."""
    gs = glyphset if glyphset is not None else font.getGlyphSet()
    out = {}
    for name in font.getGlyphOrder():
        pen = DecomposingRecordingPen(gs)
        try:
            gs[name].draw(pen)
        except Exception:
            continue
        out[name] = pen.value
    return out


def median_stem(recs, cmap, chars, cuts):
    vals = []
    for ch in chars:
        name = cmap.get(ord(ch))
        if not name or name not in recs:
            continue
        s = shapes.stem_of(recs[name], cuts=cuts)
        if s:
            vals.append(s)
    return statistics.median(vals) if vals else None


def median_ink(recs, cmap, chars):
    vals = []
    for ch in chars:
        name = cmap.get(ord(ch))
        if not name or name not in recs:
            continue
        b = shapes.bbox(recs[name])
        if b:
            vals.extend([b[2] - b[0], b[3] - b[1]])
    return statistics.median(vals) if vals else None


def solve_cjk_wght(font, target_stem, chars=KANJI_SAMPLE,
                   lo=100.0, hi=900.0, tol=0.05):
    """Bisect Noto's wght axis on the median stem of ``chars``."""
    cmap = font.getBestCmap()
    cache = {}

    def stem_at(w):
        if w not in cache:
            gs = font.getGlyphSet(location={"wght": w})
            recs = {}
            for ch in chars:
                name = cmap.get(ord(ch))
                if not name or name in recs:
                    continue
                pen = DecomposingRecordingPen(gs)
                gs[name].draw(pen)
                recs[name] = pen.value
            cache[w] = median_stem(recs, cmap, chars, shapes.CJK_CUTS)
        return cache[w]

    if stem_at(lo) >= target_stem:
        return lo, stem_at(lo)
    if stem_at(hi) <= target_stem:
        return hi, stem_at(hi)
    for _ in range(40):
        mid = (lo + hi) / 2.0
        got = stem_at(mid)
        if abs(got - target_stem) < tol:
            return mid, got
        if got < target_stem:
            lo = mid
        else:
            hi = mid
    mid = (lo + hi) / 2.0
    return mid, stem_at(mid)


def lift_ascenders(rec, x_height, factor):
    """Scale everything above the x-height so the ascender clears the cap."""
    out = []
    for op, args in rec:
        new = []
        for a in args:
            if a is None:
                new.append(a)
            else:
                x, y = a
                new.append((x, y if y <= x_height else x_height + (y - x_height) * factor))
        out.append((op, tuple(new)))
    return out


# ---------------------------------------------------------------------------


def plan_latin(style, ideal_stem):
    """Measure the achieved stem of the static Iosevka face."""
    f = TTFont(IOSEVKA % style, lazy=False)
    gs = f.getGlyphSet()
    pen = DecomposingRecordingPen(gs)
    gs[f.getBestCmap()[ord("H")]].draw(pen)
    got = shapes.stem_of(pen.value) * LATIN_XS
    f.close()
    return got


def build_latin(style, italic, targets):
    """Return {name: recording}, cmap, and a report for one face's Latin."""
    stem_t, bar_t, xs = targets
    src_style = _italic_style(style) if italic else style
    path = IOSEVKA % src_style
    f = TTFont(path, lazy=False)
    gs = f.getGlyphSet()
    cmap = f.getBestCmap()
    recs = outlines(f, gs)
    x_height = f["OS/2"].sxHeight
    cap = f["OS/2"].sCapHeight
    # Land the ascender where SF Mono puts it: 738 against a cap of 704.6.
    # Only the part above the x-height moves, so the factor is larger than the
    # ratio of the heights themselves.
    lift = ((SF_ASCENDER / SF_CAP) * cap - x_height) / (cap - x_height)
    src_angle = float(f["post"].italicAngle)
    f.close()

    # The other zero comes from the matching unslashed static plan.  Put it in
    # the same record set before any transform so it follows the exact Latin
    # path: width scale, rhythm, bar correction, centring and overlap removal.
    other = TTFont(IOSEVKA_UNSLASHED % src_style, lazy=False)
    other_gs = other.getGlyphSet()
    other_name = other.getBestCmap()[ord("0")]
    pen = DecomposingRecordingPen(other_gs)
    other_gs[other_name].draw(pen)
    recs["zero.unslashed"] = pen.value
    other.close()

    # Everything between here and the final shear happens upright, even for the
    # italics.  Two of the operations below only make sense on a standing
    # drawing: `lift_ascenders` moves points in y while leaving x alone, which
    # on a slanted stem would bend it; and the anisotropic bar correction works
    # by scaling one axis by twenty, which on a stem already leaning 10 degrees
    # lays it almost flat and then erodes across it instead of along it.  That
    # was worth four to five units of stem on every italic face.
    #
    # Standing an italic master up does not turn it into the upright design --
    # the single-storey `a` and the cursive `f` stay -- it only holds the
    # drawing still while it is reshaped.
    def upright(rec, name=None, is_ascender=False):
        """Everything that must happen on a standing drawing."""
        r = rec
        if italic:
            r = shapes.shear(r, 0.0, pivot_y=SF_CAP / 2, src_angle_deg=src_angle)
        if is_ascender:
            r = lift_ascenders(r, x_height, lift)
        # Geist Mono is already a 600-unit monospace with every glyph centred
        # on x = 300.  Scaling about x = 0 moved that centre to 275 -- the whole
        # Latin sat 25 units, 4.2 % of the cell, left of the CJK it pairs with.
        r = shapes.scale_about(r, xs, 1.0, LATIN_ADV / 2.0, 0.0)
        # U+2742 has nested radial counters; anisotropic dilation created
        # an extra hole in Medium. Preserve its source topology.
        if abs(bar_delta) > 0.5 and name != cmap.get(0x2742):
            r, took = shapes.adjust_bars_graded(r, bar_delta, tag=name)
            bar_steps[took] = bar_steps.get(took, 0) + 1
        return r

    # The pivot is the whole of the spacing question for an italic monospace.
    # Iosevka leans its own italic about the baseline, which walks every tall
    # glyph left by its full height times the tangent: its `1` and `l` sit 52
    # units left of the cell centre while `f` sits 47 right, a 100-unit spread
    # in a 600-unit cell.  Leaning about the middle of the cap instead splits
    # that error either side of the reference line, so a glyph centred upright
    # comes back centred.
    # Iosevka leans its own italic about the baseline, which walks every tall
    # glyph left by its whole height times the tangent: its `1` and `l` land 52
    # units left of the cell centre while `f` lands 47 right, a 100-unit spread
    # in a 600-unit cell.  Standing the drawing up and laying it back down
    # about the same pivot is the identity, so the sandwich does not fix that
    # -- it only holds the glyph still while it is reshaped.  The centring has
    # to be asked for.
    #
    # It has to be asked for *after* the lean, too.  Shearing does not move a
    # bounding box by a predictable amount: it moves each point by its own
    # height, so how far the box travels depends on where the glyph keeps its
    # ink.  Centring the standing `1` still left it 51 units off once leaned,
    # because a `1` is a stem and a flag with nothing at the foot.
    #
    # Only the letters and digits.  They are the set the width rhythm already
    # recognises, so this cannot reach a tile, and a column of figures is where
    # an even cell is the whole point.  Everything else keeps Iosevka's own
    # placement.
    def centre(r, name):
        if base_char(name) is None:
            return r
        box = shapes.bbox(r)
        if not box:
            return r
        off = (box[0] + box[2]) / 2.0 - LATIN_ADV / 2.0
        return shapes.translate(r, -off) if abs(off) >= 0.5 else r

    def finish(r):
        return shapes.shear(r, ITALIC_ANGLE, pivot_y=SF_CAP / 2) if italic else r

    # Where a slanted letter sits in its cell.
    #
    # The shear runs about one height for the whole alphabet, and the glyph is
    # then put back on the middle of the cell by its bounding box.  On a
    # slanted glyph that box is no longer the glyph's centre: it is set by
    # whichever two points lean furthest apart.  `1` is the clearest case --
    # its box is the width of the foot serif, which sits on the baseline and
    # barely moves, so centring the box pins the serif where the upright had
    # it and leaves the stem above it carrying the whole slant to the right.
    # It measured 42 units out of a 600 cell, 7 %, with `l` at 54 and `i` at
    # 46; `7`, whose box is its top bar, was thrown 32 the other way.
    #
    # So the letters are placed by ink instead of by box: the slanted glyph is
    # moved until its ink balances where the upright's ink balanced.  That is
    # the same as shearing each letter about its own centre of ink rather than
    # about the alphabet's cap height, and it leaves the upright faces
    # untouched by construction.  Only letters and digits -- the glyphs
    # `centre` already governs -- are moved; punctuation keeps the plain
    # oblique behaviour, where a period low in the cell is meant to drift with
    # the slant.
    def place_slanted(slanted, standing, name):
        if not italic or base_char(name) is None:
            return slanted
        here = shapes.centroid(slanted)
        there = shapes.centroid(standing)
        if here is None or there is None:
            return slanted
        off = there[0] - here[0]
        return shapes.translate(slanted, off) if abs(off) >= 0.5 else slanted

    hname = cmap[ord("H")]
    bar_delta = 0.0                       # measured on the upright probe below
    bar_steps = {}
    probe = upright(recs[hname])
    bar_delta = bar_t - shapes.bar_of(probe)
    h_box = shapes.bbox(upright(recs[hname]))
    h_ink = h_box[2] - h_box[0]

    asc_names = {cmap[ord(c)] for c in ASCENDERS if ord(c) in cmap}

    # Which letter a glyph is a variant or an accented form of, so that `aacute`
    # is reshaped exactly like `a` and the two still look like one alphabet.
    name_to_cp = {}
    for cp, n in sorted(cmap.items()):
        name_to_cp.setdefault(n, cp)

    def base_char(name):
        if name == "zero.unslashed":
            return "0"
        cp = name_to_cp.get(name.split(".")[0])
        if cp is None:
            return None
        d = unicodedata.normalize("NFD", chr(cp))
        return d[0] if d and d[0] in SF_WIDTH else None

    col = STYLES_INDEX[style]
    width_stats = {"moved": 0, "clamped": [], "reverted": []}

    def rhythm(r, name):
        """Give the glyph the share of the cell SF Mono gives it."""
        base = base_char(name)
        if base is None:
            return r
        box = shapes.bbox(r)
        if not box or box[2] - box[0] < 1.0:
            return r
        now = (box[2] - box[0]) / h_ink
        want = SF_WIDTH[base][col]
        sx = want / now
        if abs(sx - 1.0) < WIDTH_DEADBAND:
            return r
        if abs(sx - 1.0) > WIDTH_CLAMP:
            width_stats["clamped"].append((name, round(sx, 3)))
            sx = 1.0 + math.copysign(WIDTH_CLAMP, sx - 1.0)
        cx = (box[0] + box[2]) / 2
        scaled = shapes.scale_about(r, sx, 1.0, cx, 0.0)
        # The cell is what changes; the weight is not.  Scaling x by sx took the
        # stems down with it, so put them back exactly.
        restored = shapes.adjust_stems(scaled, stem_t * (1.0 - sx), tag=name)
        if restored is scaled and abs(stem_t * (1.0 - sx)) > 0.5:
            width_stats["reverted"].append(name)   # the stem could not be rebuilt
            return r
        width_stats["moved"] += 1
        return restored

    # Box drawing, block elements and shades are not letters: they are tiles
    # that have to meet their neighbours exactly, which is why Geist draws them
    # from -5 to 605 and lets adjacent cells overlap by five units.  The width
    # scale shrank the rule to 554 and left a 46-unit gap in every run of `-`,
    # and the full block to 550, striping `#` fills.  Nor may they lean: a
    # slanted table border is not an italic, it is a broken table.  They pass
    # through exactly as drawn.
    #
    # Braille and the legacy-computing blocks are the same kind of thing and
    # were being leaned: a Braille cell's six dots are at fixed positions in
    # the cell, and a sextant that leans no longer meets the sextant above it.
    # They are deliberately off centre -- ⢸ sits 150 units right because that
    # is where its dots are -- so they must also be kept out of any centring.
    #
    # U+1CC00-1CEFF and U+1FB00-1FBFF are deliberately NOT here.  They read
    # like more of the same and are not: Iosevka draws a couple of dozen of
    # those wider than the cell, and they only fit because `recentre_symbol`
    # shrinks them.  Calling them tiles skipped that and 23 then 17 glyphs
    # spilled into the neighbouring cell.  Braille and box drawing were checked
    # the same way and neither spills, so those two are the whole set.
    TILE_BLOCKS = [(0x2500, 0x259F), (0x2800, 0x28FF)]
    graphic_names = {cmap[cp] for lo, hi in TILE_BLOCKS
                     for cp in range(lo, hi + 1) if cp in cmap}

    def recentre_symbol(r, name):
        """A symbol whose ink leaves its cell is ink the neighbour has to share.

        Geist draws U+25B6 from -54 to 451 and U+25C0 from 149 to 654 -- the
        pair is off centre by 101 units each way, where its own U+25B2, U+25BC
        and U+25CF all sit on 300.  Letters are left alone: a slanted `f` is
        meant to reach past the cell, and an accent is placed by its base.
        """
        box = shapes.bbox(r)
        if not box or unicodedata.category(chr(name_to_cp.get(name, 0))) in ("Mn", "Me", "Cf"):
            return r
        if box[0] >= 0.0 and box[2] <= LATIN_ADV:
            return r
        width = box[2] - box[0]
        if width > LATIN_ADV:
            g = LATIN_ADV / width
            cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
            r = shapes.scale_about(r, g, 1.0, cx, cy)
            box = shapes.bbox(r)
        off = (box[0] + box[2]) / 2.0 - LATIN_ADV / 2.0
        return shapes.translate(r, -off) if abs(off) >= 1.0 else r

    # Optical weight, not mechanical weight.
    #
    # The Latin axis hands every glyph the same stem, which is exactly uniform
    # on the measuring machine and slightly wrong to the eye.  A capital is
    # cap-height tall with open counters, so at the stem of a lowercase it
    # reads lighter than one; SF Mono answers that by drawing its capitals
    # 2.9 % heavier than its lowercase -- 85.4 against 83.0 -- rather than
    # equal.  Inori was flat 84.0 across both, and the lowercase won.
    #
    # Iosevka's `=` has the opposite problem.  Its bars leave the width scale
    # at 75 where this design's own bar target is 77.8 and SF Mono's `=` is 94,
    # so the busiest operator in the alphabet is the lightest mark on the line.
    # It is corrected to the design's target, not to SF Mono's: 94 would make
    # `=` heavier than the stems around it.
    #
    # Both happen on the standing drawing, before the italic lean, for the same
    # reason the global bar correction does -- the anisotropic dilation scales
    # one axis by twenty, which lays a leaning stem flat and then erodes across
    # it instead of along it.
    CAPS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    equals_name = cmap.get(ord("="))
    optical_stats = {"caps": 0, "equals": 0}

    def optical(r, name):
        if base_char(name) in CAPS:
            box = shapes.bbox(r)
            grown, ok = shapes.dilate_checked(r, stem_t * CAP_OPTICAL, name)
            gb = shapes.bbox(grown) if ok else None
            if not ok or not box or not gb or gb[3] - gb[1] < 1.0:
                return r
            # An isotropic dilation also grows the glyph by half the amount at
            # the top and at the foot, which would lift the capitals off the
            # cap line and drop them through the baseline.  Put the vertical
            # box back exactly where it was; the y scale is under a half
            # percent, far below the stem it is protecting.
            sy = (box[3] - box[1]) / (gb[3] - gb[1])
            optical_stats["caps"] += 1
            return shapes.transform(
                grown, Transform(1, 0, 0, sy, 0, box[1] - gb[1] * sy))
        if name is not None and name == equals_name:
            now = shapes.bar_of(r)
            if now is None or abs(bar_t - now) < 0.5:
                return r
            grown, ok = shapes.adjust_bars_checked(r, bar_t - now, tag=name)
            if ok:
                optical_stats["equals"] += 1
                return grown
        return r

    out = {}
    for name, rec in recs.items():
        if not rec:
            out[name] = rec
            continue
        if name in graphic_names:
            # Tiles have to meet their neighbours exactly, and a leaning table
            # border is not an italic, it is a broken table.
            out[name] = shapes.remove_overlap(rec, name)
            continue
        r = upright(rec, name, name in asc_names)
        r = rhythm(r, name)
        r = optical(r, name)
        placed = centre(recentre_symbol(finish(r), name), name)
        if italic:
            placed = place_slanted(
                placed, centre(recentre_symbol(r, name), name), name)
        out[name] = shapes.remove_overlap(placed, name)

    # A terminal column needs every digit on the same pixel rows.  Iosevka's
    # curved digits carry overshoot while the flat ones do not, so normalize
    # their vertical ink boxes to zero's box before hinting.  The alternate
    # zero follows the same map and remains exactly the same height.
    zero_box = shapes.bbox(out[cmap[ord("0")]])
    for name in ({cmap[ord(ch)] for ch in "0123456789"} |
                 {"zero.unslashed"}):
        rec = out.get(name)
        box = shapes.bbox(rec) if rec else None
        if not box or not zero_box or box[3] == box[1]:
            continue
        sy = (zero_box[3] - zero_box[1]) / (box[3] - box[1])
        out[name] = shapes.transform(
            rec, Transform(1, 0, 0, sy, 0, zero_box[1] - box[1] * sy))

    # Curved extrema can still fall on a different raster row from a flat edge
    # even when their design-space boxes are identical.  Join a 24x8-unit cap
    # to an existing top and bottom stroke.  It is below visual resolution,
    # preserves contour counts, and makes the shared extrema real ink at every
    # 9--24 px check size instead of an antialiasing accident.
    def cap_edge(rec, top, tag):
        box = shapes.bbox(rec)
        y = box[3] if top else box[1]
        inside = y - 6 if top else y + 6
        spans = shapes.spans_h(shapes._flatten(rec), inside)
        if not spans:
            return rec
        x0, x1 = max(spans, key=lambda span: span[1] - span[0])
        width = min(24.0, (x1 - x0) * 0.7)
        cx = (x0 + x1) / 2.0
        y0, y1 = ((y - 8, y) if top else (y, y + 8))
        cap = [("moveTo", ((cx - width / 2, y0),)),
               ("lineTo", ((cx + width / 2, y0),)),
               ("lineTo", ((cx + width / 2, y1),)),
               ("lineTo", ((cx - width / 2, y1),)),
               ("closePath", ())]
        return shapes.remove_overlap(rec + cap, tag)

    for name in ({cmap[ord(ch)] for ch in "0123456789"} |
                 {"zero.unslashed"}):
        if out.get(name):
            out[name] = cap_edge(cap_edge(out[name], True, name), False, name)

    digits = sorted(shapes.bbox(out[cmap[ord(c)]]) for c in "0123456789")
    skew = max(abs((b[0] + b[2]) / 2.0 - LATIN_ADV / 2.0) for b in digits)
    report = dict(source=os.path.basename(path),
                  achieved=round(shapes.stem_of(probe), 2),
                  digit_skew=round(skew, 1),
                  bar_delta=round(bar_delta, 2), lift=round(lift, 3),
                  bars="full %d / two-thirds %d / a third %d / none %d"
                       % (bar_steps.get(1.0, 0), bar_steps.get(0.66, 0),
                          bar_steps.get(0.33, 0), bar_steps.get(0.0, 0)),
                  widths=width_stats["moved"],
                  clamped=len(width_stats["clamped"]),
                  reverted=len(width_stats["reverted"]),
                  optical="caps %d / = %d"
                          % (optical_stats["caps"], optical_stats["equals"]))
    return out, cmap, report


def frame_of(recs, cmap, chars):
    """Median ink width, height and vertical centre over a sample."""
    w, h, c = [], [], []
    for ch in chars:
        name = cmap.get(ord(ch))
        if not name or name not in recs:
            continue
        b = shapes.bbox(recs[name])
        if not b:
            continue
        w.append(b[2] - b[0])
        h.append(b[3] - b[1])
        c.append((b[1] + b[3]) / 2)
    if not w:
        return None
    return (statistics.median(w), statistics.median(h), statistics.median(c))




def _voiced_body(rec):
    """The bounding box of a voiced kana without its dakuten.

    The mark is two or three small contours in the top right corner.  Reading
    it off geometry rather than off a contour index keeps this working when the
    source reorders its outlines, and a glyph whose mark cannot be told apart
    simply reports its whole box -- which is the old behaviour, not a wrong
    one.
    """
    boxes = []
    for contour in shapes.contours(rec):
        box = shapes.bbox(contour)
        if box:
            boxes.append(box)
    if not boxes:
        return None
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)
    width, height = x1 - x0, y1 - y0
    body = [b for b in boxes
            if not ((b[2] - b[0]) < width * 0.30
                    and (b[3] - b[1]) < height * 0.30
                    and b[0] > x0 + width * 0.55
                    and b[1] > y0 + height * 0.55)]
    if not body or len(body) == len(boxes):
        return (x0, y0, x1, y1)
    return (min(b[0] for b in body), min(b[1] for b in body),
            max(b[2] for b in body), max(b[3] for b in body))


def kana_rhythm(out, cmap):
    """Per-kana vertical nudges, as {glyph name: dy}.

    Two passes, in this order.  The unvoiced kana are placed against
    Hiragino's own character-by-character judgement, scaled by
    KANA_RHYTHM_GAIN; then each voiced kana is put where its unvoiced partner
    now sits, so か and が share a line.  Both are pure translations -- no
    curve, stroke weight, contour count or advance changes -- so there is no
    outline to damage and nothing here can fail the way a boolean pass can.
    """
    centre = {}
    for ch in list(HIRAGINO_KANA_RHYTHM) + list(VOICED_BASE):
        name = cmap.get(ord(ch))
        rec = out.get(name) if name else None
        if not rec:
            continue
        box = _voiced_body(rec) if ch in VOICED_BASE else shapes.bbox(rec)
        if box:
            centre[ch] = (box[1] + box[3]) / 2.0

    shift = {}
    for chars, lift_sample in (
            ([c for c in HIRAGINO_KANA_RHYTHM if ord(c) < 0x30A0], HIRA_SAMPLE_FULL),
            ([c for c in HIRAGINO_KANA_RHYTHM if ord(c) >= 0x30A0], KATA_SAMPLE_FULL)):
        have = [c for c in chars if c in centre]
        if not have:
            continue
        mean = statistics.mean(centre[c] for c in have)
        moved = {ch: mean + HIRAGINO_KANA_RHYTHM[ch] * CJK_SCALE * KANA_RHYTHM_GAIN
                 for ch in have}

        # The class as a whole must not move.  The lift a few lines up put the
        # median of `lift_sample` on Hiragino's measured rise, so that median
        # -- the same statistic over the same characters -- is what has to come
        # back unchanged.  Re-centring on the outcome rather than on the table
        # is what makes this exact: it holds however the table is edited, and
        # it holds even though the table's characters and the lift sample's are
        # not the same set.
        anchor = [c for c in lift_sample if c in centre] or have
        drift = (statistics.median(moved[c] for c in anchor if c in moved)
                 - statistics.median(centre[c] for c in anchor))
        for ch in have:
            shift[cmap[ord(ch)]] = (moved[ch] - drift) - centre[ch]

    for voiced, plain in VOICED_BASE.items():
        if voiced not in centre or plain not in centre:
            continue
        name = cmap.get(ord(voiced))
        if not name:
            continue
        plain_name = cmap.get(ord(plain))
        moved = shift.get(plain_name, 0.0)
        shift[name] = (centre[plain] + moved) - centre[voiced]

    return {n: d for n, d in shift.items() if abs(d) >= 0.5}


def read_vert(font):
    """The source's own vertical-form substitutions, as {src: dst}."""
    out = {}
    if "GSUB" not in font:
        return out
    g = font["GSUB"].table
    for rec in g.FeatureList.FeatureRecord:
        if rec.FeatureTag not in ("vert", "vrt2"):
            continue
        for i in rec.Feature.LookupListIndex:
            for st in g.LookupList.Lookup[i].SubTable:
                out.update(getattr(st, "mapping", {}) or {})
    return out




def plan_cjk_wghts(font, target_stem, want_frame):
    """Return Noto axis locations after accounting for the uniform frame fit."""
    cmap = font.getBestCmap()
    target_w = want_frame[0] * CJK_SCALE
    target_h = want_frame[1] * CJK_SCALE
    probe_wght, _ = solve_cjk_wght(font, target_stem)
    probe_gs = font.getGlyphSet(location={"wght": probe_wght})
    probe_recs = {}
    for ch in set(FRAME_SAMPLE + KANJI_SAMPLE):
        name = cmap.get(ord(ch))
        if not name or name in probe_recs:
            continue
        pen = DecomposingRecordingPen(probe_gs)
        probe_gs[name].draw(pen)
        probe_recs[name] = pen.value
    pw, ph, _ = frame_of(probe_recs, cmap, FRAME_SAMPLE)
    pstem = median_stem(probe_recs, cmap, KANJI_SAMPLE, shapes.CJK_CUTS)
    scale = 1.0
    for _ in range(8):
        delta = target_stem - pstem * scale
        scale = ((target_w - delta) / pw +
                 (target_h - delta) / ph) / 2.0
    kw, _ = solve_cjk_wght(font, target_stem / scale)
    hw, _ = solve_cjk_wght(
        font, target_stem * _at(HIRAGINO_HIRA_STEM, target_stem) / scale,
        HIRA_BAR_SAMPLE)
    tw, _ = solve_cjk_wght(
        font, target_stem * _at(HIRAGINO_KATA_STEM, target_stem) / scale,
        KATA_BAR_SAMPLE)
    return kw, hw, tw


# ------------------------------------------------------------------- 手描き
#
# ここまでの補正は全部「測って、動かす」だった。比率を合わせ、クラスを持ち上
# げ、一字ずつセルに落ち着かせた。数字の上ではヒラギノを上回っている。それで
# も並べると別の字に見えるのは、差が箱の中の *描き方* にあるからで、拡大でも
# 平行移動でも届かない。`と` は墨box比 0.986x0.994 ―― 同じ大きさの別の字だ。
#
# 最初はそこを変形で詰めた。`と` の1画目を 24.3 度から 13.7 度へ立て、2画目を
# 寝かせ、たわみを直線に載せ直す。数字はヒラギノに寄ったが、字ごとに新しい変
# 形を足すことになり、`や` では 3画目を立てたら水平シアーが 1/cos だけ太らせ、
# `ふ` に至っては体の脚の向きが違って腕が左へループした。変形は「輪郭を直接
# いじれない」ことへの回り道でしかない。
#
# なので絵から起こす。`drawings/` にある手描きを二値化して輪郭を追い、いまその
# 字が占めている墨boxに載せ、このウェイトの線幅に合わせる。濁点や小書きは元の
# グリフから持ってきて体だけ差し替える。ヒラギノは測るだけで、写しはしない。
#
# 変形版のコードはここにあったが全部消した。手描きの交点を変形でいじるのは、
# そもそも手描きにした理由と矛盾する ―― `と` の2画目をヒラギノの勾配へ回した
# ときは、数字が 0.290 対 0.289 で合ったまま 1画目の足が垂れたトゲになった。
# 勾配を変えたいなら描き直す。

DRAWINGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "drawings")
# 絵と、スマホのスクショなら切り出す範囲 (None なら画像全体)
HAND_SOURCE = {
    "と": ("to.png", None),
    "や": ("ya.jpg", None),
    "き": ("ki.png", None),
    "ふ": ("fu-screenshot.png", (660, 2150)),
    "さ": ("sa.png", None),
}
# `さ` と `き` は横画より下が同じ字で、ヒラギノもそう描いている ―― 同じ椀を、
# `き` では横画がもう一本入るぶん 0.05 下げてあるだけ。手で別々に描くと椀が
# 二つになる (下半分の IoU 0.639) ので、`さ` は継ぎ目から下を `き` からもらう。
HAND_GRAFT = {"さ": ("き", 0.46)}
# 手描きの字から作る字。True は濁点・半濁点を持つもの。
HAND_DERIVE = {
    "と": [("ど", True)],
    "や": [("ゃ", False)],
    "き": [("ぎ", True)],
    "ふ": [("ぶ", True), ("ぷ", True)],
    "さ": [("ざ", True)],
}
HAND_DRAWN = tuple(HAND_SOURCE)
HAND_ALL = HAND_DRAWN + tuple(
    ch for outs in HAND_DERIVE.values() for ch, _ in outs)


#: Friday Mono v47/v48 (and every later Mono up to 4.92) shipped the per-glyph
#: kana bar pass; Friday Sans does not.  A new Mono weight sets this True so it
#: is built the same way as the weights it sits beside.
KANA_BAR_MATCH_DEFAULT = os.environ.get("FRIDAY_KANA_BAR_MATCH") == "1"


def generated_hand_outlines(out, cmap):
    """Hand kana for a weight with no approved proof, by the approved route.

    `shared_master.build` is what produced approved-hand-outlines.json for
    Regular / Medium / Bold: one fixed centreline per character, stroke weight
    fitted to this face's own Noto-derived neighbours.  The two edits made
    to the approved file afterwards are replayed: `thin_ki.py` (き -2.5) and
    `fix_voiced_bodies.py` (ぎ ど ざ take the plain drawing as their body).
    """
    sys.path.insert(0, HERE)
    from tools import shared_master
    import thin_ki
    import fix_voiced_bodies as voiced
    from fontTools.misc.transform import Transform
    targets = {ch: out[cmap[ord(ch)]] for ch in "しつか" + "".join(HAND_ALL)}
    glyphs, _ = shared_master.build(targets)
    ki, ok = shapes.dilate_checked(glyphs["き"], thin_ki.AMOUNT, "き")
    if not ok or shapes._contours(ki) != shapes._contours(glyphs["き"]):
        raise ValueError("き: the generated erosion did not take")
    glyphs["き"] = ki
    for v, plain in voiced.BODIES.items():
        parts = voiced.contours(glyphs[v])
        body, mark = parts[0], [x for c in parts[1:] for x in c]
        bb, kb = shapes.bbox(body), shapes.bbox(glyphs[plain])
        room = (bb[2] - bb[0]) - (kb[2] - kb[0])
        assert -1.0 <= room < 5.0, (v, "width", round(room, 2))
        dx = (bb[0] + bb[2]) / 2.0 - (kb[0] + kb[2]) / 2.0
        dy = bb[3] - kb[3]
        moved = shapes.transform(glyphs[plain], Transform(1, 0, 0, 1, dx, dy))
        merged = moved + mark
        assert (shapes._contours(shapes.remove_overlap(merged, v))
                == shapes._contours(moved) + shapes._contours(mark)), v
        glyphs[v] = merged
    return glyphs


def hand_redraw(out, cmap, style):
    """Use one fixed hand-drawing-derived skeleton across all three weights.

    Only stroke weight follows this face's unchanged Noto-derived neighbours.
    Centreline paths are never refitted by weight. Ya uses one frozen
    accepted outline with symmetric weight offsets.
    """
    # Freeze exactly the user-approved proof, avoiding a new optical-width
    # fit against pre-rounding source outlines during production.
    with open(os.path.join(DRAWINGS, "approved-hand-outlines.json"), encoding="utf-8") as fh:
        approved = json.load(fh)
    with open(os.path.join(DRAWINGS, "vector-masters.json"), "rb") as fh:
        current_hash = hashlib.sha256(fh.read()).hexdigest()
    if approved["master_sha256"] != current_hash:
        raise ValueError("Approved proof no longer matches the current master")
    if style in approved["styles"] and not os.environ.get("FRIDAY_HAND_REGENERATE"):
        replacements = approved["styles"][style]
    else:
        replacements = generated_hand_outlines(out, cmap)
    for ch, rec in replacements.items():
        out[cmap[ord(ch)]] = rec
    return list(replacements), []


# ------------------------------------------------------- 終筆の切り落とし
#
# `あ` の2画目と `め` の1画目は椀を横切って終わる。ヒラギノはその終筆を椀の縁で
# 止めるので、外から見えるのは椀の輪郭だけになる。Noto は椀を越えたところで切
# るので、椀の下に四角い切り口が突き出す ―― 抜けた払いではなく、ただの出っ張
# りに見える。
#
# カタカナの `タ` `ダ` も同じで、3画目が2画目の払いを横切ったあと右下へ突き
# 出す。ヒラギノにはその位置に終筆そのものが無い ―― 払いの中で終わっている。
#
# 直すのは出っ張りの分だけ。横切った画の外へ出た部分を、両側の接合点を結ぶ線
# で落とす。骨格も勾配も線幅も曲率も動かさない。落ちるのは `あ` で墨の 2.2 %、
# `め` で 2.9 %、`タ` で 5.2 %、`ダ` で 4.7 % で、横切られた画はそのまま残る。
#
# ここに字を足すときは必ず目で確かめること。終筆を探す規則は「突起」と「正当
# な終筆」を見分けられない ―― 仮名 100 字に当てると `ノ` の払いを半分（墨の
# 50 %）落としてしまう。効くのは、横切られた画が別にある字だけ。
TRIM_STUB = ("あ", "め", "タ", "ダ")


def _terminal_stub(rec):
    """The straight terminal that pokes past the bowl, with its two joins.

    Both characters have two straight terminals low in the glyph.  The one to
    cut is the one that sits higher: the other is the character's own last
    stroke, and it is meant to end in the open.

    Height alone is not enough to name the edge, though.  A stub is a
    parallelogram -- the flat tip and the join line it stands on are its two
    parallel sides -- and where the flank next to the tip happens to be drawn
    straight rather than curved, that flank is a candidate too, and it sits
    higher than the tip it belongs to.  Choosing it puts the cut along the
    stub instead of across it and leaves a triangle behind, which is what
    Medium did to `タ` and `ダ`: their flanks come out of the reshaper as
    line segments while Regular and Bold keep theirs as curves.  So the
    candidates are tried from the top down and the first one whose join line
    comes back parallel to it -- as the far side of a parallelogram must --
    is the terminal.
    """
    outer = max(shapes.contours(rec), key=lambda c: abs(shapes.area(c)))
    box = shapes.bbox(rec)
    pts, kinds = [], []
    for op, args in outer:
        if op in ("moveTo", "lineTo"):
            pts.append(args[0])
            kinds.append(op)
        elif op in ("curveTo", "qCurveTo"):
            pts.append(args[-1])
            kinds.append(op)
    n = len(pts)
    cands = []
    for i in range(n):
        if kinds[(i + 1) % n] != "lineTo":
            continue
        a, b = pts[i], pts[(i + 1) % n]
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        if length < 20.0:
            continue
        middle = (a[1] + b[1]) / 2.0
        if middle > box[1] + (box[3] - box[1]) * 0.32:
            continue
        cands.append((middle, i, length))
    if not cands:
        return None
    cands.sort(reverse=True)
    # Walk off the terminal to the first point that is really somewhere else:
    # these outlines carry doubled and near-doubled points at the corners.
    def turn_at(i):
        a, b, c = pts[(i - 1) % n], pts[i], pts[(i + 1) % n]
        u = (b[0] - a[0], b[1] - a[1])
        v = (c[0] - b[0], c[1] - b[1])
        return abs(math.degrees(math.atan2(u[0] * v[1] - u[1] * v[0],
                                           u[0] * v[0] + u[1] * v[1])))

    def away(start, step, length):
        here, anchor = start, pts[start]
        for _ in range(6):
            here = (here + step) % n
            if math.hypot(pts[here][0] - anchor[0],
                          pts[here][1] - anchor[1]) > length * 0.25:
                break
        # One more step, if the next point is the corner where the crossed
        # stroke's edge turns into this one's flank.  `タ` puts that corner
        # 36 units further back at 80 degrees, and stopping short of it left
        # the stub poking out by exactly that much.  The distance test is
        # what keeps `め` where it is: its nearest sharp corner is 187 units
        # away, which is the far side of the bowl and not a join at all.
        nxt = (here + step) % n
        gap = math.hypot(pts[nxt][0] - pts[here][0], pts[nxt][1] - pts[here][1])
        if turn_at(nxt) >= 45.0 and gap < length * 1.5:
            here = nxt
        return here
    def parallel(u, v):
        """The angle between two undirected edges, in degrees."""
        a = math.degrees(math.atan2(u[1], u[0])) % 180.0
        b = math.degrees(math.atan2(v[1], v[0])) % 180.0
        d = abs(a - b)
        return min(d, 180.0 - d)

    # 20 degrees found every terminal at Regular / Medium / Bold.  Light's
    # thinner join lands at 20.4 on `あ`; a second, slightly wider pass runs
    # only when the first finds nothing, so the shipped weights are unchanged.
    for limit in (20.0, 22.0):
        found = _first_parallel(cands, pts, n, away, parallel, limit)
        if found is not None:
            return found
    return None


def _first_parallel(cands, pts, n, away, parallel, limit):
    for _, i, length in cands:
        head = away(i, -1, length)
        tail = away((i + 1) % n, 1, length)
        ring, j = [], head
        while True:
            ring.append(pts[j])
            if j == tail:
                break
            j = (j + 1) % n
        edge = (pts[(i + 1) % n][0] - pts[i][0],
                pts[(i + 1) % n][1] - pts[i][1])
        join = (pts[tail][0] - pts[head][0], pts[tail][1] - pts[head][1])
        if math.hypot(*join) < 1.0 or parallel(edge, join) > limit:
            continue
        tip = ((pts[i][0] + pts[(i + 1) % n][0]) / 2.0,
               (pts[i][1] + pts[(i + 1) % n][1]) / 2.0)
        return ring, tip
    return None


def _stub_cutter(rec):
    """A parallelogram covering everything the stub puts past the bowl.

    Cutting with a polygon that traces the stub's own outline does not work:
    its edges are the chords of the outline's curves, so the sliver between
    chord and curve survives as a zero-width spike -- `あ` kept a hairline
    running back down to the old tip.  Cutting with a shape whose only
    contact is the join line leaves the boundary exactly as the bowl drew it.
    """
    found = _terminal_stub(rec)
    if found is None:
        return None
    ring, tip = found
    if len(ring) < 3:
        return None
    head, tail = ring[0], ring[-1]
    dx, dy = tail[0] - head[0], tail[1] - head[1]
    span = math.hypot(dx, dy)
    if span < 1.0:
        return None
    # Outward is whichever side of the join line the terminal itself is on.
    n = (dy / span, -dx / span)

    def offset(p):
        return (p[0] - head[0]) * n[0] + (p[1] - head[1]) * n[1]

    if offset(tip) < 0:
        n = (-n[0], -n[1])
    depth = max(offset(p) for p in ring)
    # A stub stands proud of its own join line by about its own width.  Run
    # this a second time and the terminal it finds is the join line left by
    # the first pass, which stands proud of nothing -- and the deepest ink on
    # the far side would be the bowl.  Anything shallow is already done.
    if offset(tip) < span * 0.30 or depth < span * 0.30:
        return None
    # The terminal leans back a little past its own join -- a tenth of the
    # join line on `あ` at Bold, a quarter at Regular -- so the band has to
    # reach that far or a corner of the stub survives the cut.  Widening it
    # is safe because the cut only ever takes ink that is past the join line,
    # and the bowl is on the near side of it.
    along = [((p[0] - head[0]) * dx + (p[1] - head[1]) * dy) / (span * span)
             for p in ring]
    lo, hi = min(along) - 0.03, max(along) + 0.03
    depth += 10.0

    def corner(t, out):
        return (head[0] + dx * t + n[0] * depth * out,
                head[1] + dy * t + n[1] * depth * out)

    return [("moveTo", (corner(lo, 0),)), ("lineTo", (corner(lo, 1),)),
            ("lineTo", (corner(hi, 1),)), ("lineTo", (corner(hi, 0),)),
            ("closePath", ())]


def trim_stubs(out, cmap):
    """Cut the terminals of あ め back to the bowl they cross."""
    done = []
    for ch in TRIM_STUB:
        name = cmap.get(ord(ch))
        rec = out.get(name) if name else None
        if not rec:
            continue
        cut = _stub_cutter(rec)
        if cut is None:
            continue
        path = pathops.Path()
        pathops.difference([shapes.to_path(rec)], [shapes.to_path(cut)],
                           path.getPen())
        trimmed = shapes.prune(shapes.from_path(path))
        # Cutting a stub off may not open, close or split anything, and it
        # may not eat the stroke: a tenth of the glyph is not a stub.
        if shapes._contours(trimmed) != shapes._contours(rec):
            continue
        if abs(shapes.area(trimmed)) < abs(shapes.area(rec)) * 0.90:
            continue
        out[name] = trimmed
        done.append(ch)
    return done


def zero_advance(cp):
    return unicodedata.category(chr(cp)) in ("Mn", "Me", "Cf")


_UVS_CACHE = None

def release_uvs():
    global _UVS_CACHE
    if _UVS_CACHE is None:
        with TTFont(NOTO_CJK, lazy=True) as f:
            supported = jp_coverage(f.getBestCmap())
            _UVS_CACHE = {t: [(cp, n) for cp, n in pairs if cp in supported]
                          for table in f["cmap"].tables if table.format == 14
                          for t, pairs in table.uvsDict.items()}
    return _UVS_CACHE


def build_cjk(style, target_stem, want_frame, want_centre):
    """Build CJK from Noto Sans CJK JP at measured axis locations.

    Kanji, hiragana and katakana use separate wght locations.  This reaches
    Hiragino's class stem ratios without boolean dilation; the existing bar
    correction remains because Noto's horizontal/vertical ratio is not on the
    weight axis.
    """
    f = TTFont(NOTO_CJK, lazy=False)
    source_upem = f["head"].unitsPerEm
    # Cut the source down before anything expensive touches it.  Every glyph
    # kept here is settled one at a time further down, so this is also what the
    # build time is made of.
    cmap = jp_coverage(f.getBestCmap())
    target_w = want_frame[0] * CJK_SCALE
    target_h = want_frame[1] * CJK_SCALE

    kanji_wght, hira_wght, kata_wght = plan_cjk_wghts(
        f, target_stem, want_frame)
    glyphsets = {
        "kanji": f.getGlyphSet(location={"wght": kanji_wght}),
        "hira": f.getGlyphSet(location={"wght": hira_wght}),
        "kata": f.getGlyphSet(location={"wght": kata_wght}),
    }
    vert = read_vert(f)
    names = set(cmap.values()) | set(vert) | set(vert.values())
    names.update(n for pairs in release_uvs().values() for cp, n in pairs if n)
    source_class = {}
    for cp, name in cmap.items():
        if cp in HIRAGANA:
            source_class[name] = "hira"
        elif cp in KATAKANA:
            source_class[name] = "kata"
    recs, advances = {}, {}
    for name in names:
        gs = glyphsets[source_class.get(name, "kanji")]
        pen = DecomposingRecordingPen(gs)
        try:
            gs[name].draw(pen)
        except Exception:
            continue
        recs[name] = pen.value
        advances[name] = int(round(gs[name].width))
    vert = {a: b for a, b in vert.items() if a in recs and b in recs}
    f.close()

    src_w, src_h, src_c = frame_of(recs, cmap, FRAME_SAMPLE)
    src_stem = median_stem(recs, cmap, KANJI_SAMPLE, shapes.CJK_CUTS)

    # Solve the optical size for the frame *after* the global weight offset.
    # A dilation changes both the stem and the ink box, so a single division
    # would overshoot the requested dimensions.
    scale = 1.0
    for _ in range(8):
        delta = target_stem - src_stem * scale
        scale = ((target_w - delta) / src_w +
                 (target_h - delta) / src_h) / 2.0

    # The output cell follows the codepoint, never the proportional source
    # metric.  This preserves the 600/1200 terminal grid.
    cell_of = {}
    for cp, name in cmap.items():
        want = CJK_ADV if is_fullwidth_cp(cp) else LATIN_ADV
        cell_of[name] = max(cell_of.get(name, 0), want)
    # Vertical forms are never in the character map; they inherit their cell
    # from the glyph they substitute for.
    for src, dst in vert.items():
        cell_of.setdefault(dst, cell_of.get(src, CJK_ADV))

    scaled = {}
    refitted = 0
    for name, rec in recs.items():
        if not rec:
            scaled[name] = rec
            continue
        source_advance = advances.get(name, UPEM)
        target_advance = cell_of.get(name, CJK_ADV)
        box = shapes.bbox(rec)
        # Scale about the centre of the source cell, then put that centre at
        # the centre of the output cell.  Vertical placement follows the
        # measured Hiragino centre used by the rest of the family.
        g = scale
        tx = target_advance / 2.0 - source_advance * scale / 2.0
        ty = want_centre - src_c * scale
        if target_advance == LATIN_ADV and box:
            # Half the symbols here are drawn to fill the em even though they
            # occupy one column: the star is 970 units of ink, the warning sign
            # 953, the degree-Celsius sign 936.  Fit them to the half-width
            # cell uniformly -- compressing x alone would flatten a star into
            # an ellipse -- and centre what was refitted on its own ink.
            ink = (box[2] - box[0]) * scale
            budget = LATIN_ADV * HALFWIDTH_FIT
            if ink > budget:
                g = scale * budget / ink
                ty = want_centre - (box[1] + box[3]) / 2.0 * g
                refitted += 1
            # The source cell is 1000 and the output cell is 600, so centring
            # the *cell* leaves the ink wherever the source happened to put it
            # -- beta came out 22 units right of centre.  A half-width glyph is
            # centred on its own ink, which is what a monospace means.
            tx = target_advance / 2.0 - (box[0] + box[2]) / 2.0 * g
        scaled[name] = shapes.transform(
            rec, Transform(g, 0, 0, g, tx, ty))

    achieved = median_stem(scaled, cmap, KANJI_SAMPLE, shapes.CJK_CUTS)
    global_delta = target_stem - achieved
    stem_window = area_window(global_delta, target_stem)
    kana_names = {
        cmap[cp] for cp in list(HIRAGANA) + list(KATAKANA) if cp in cmap
    }
    out = {}
    full = partial = unchanged = guarded = 0
    residual = []
    guarded_names = []
    for name, rec in scaled.items():
        if not rec or abs(global_delta) <= 0.25:
            out[name] = shapes.remove_overlap(rec, name) if rec else rec
            unchanged += bool(rec)
            continue
        base = shapes.remove_overlap(rec, name)
        base_area = abs(shapes.area(base))
        keep = shapes._contours(base)
        # v3.3: the topology rule that kana always had now applies to every
        # glyph.  `dilate_graded` returned the first step the solver did not
        # refuse, and "did not refuse" is not the same as "came back whole":
        # 攷 had the join between its two halves severed and shipped as two
        # contours, 涂 came back with a stroke drawn twice a hair apart, 懕
        # had a counter flood shut.  481 kanji in the Regular of 2026-09-04
        # carried damage of that kind.  The area window below cannot see any
        # of it -- a severed join moves the ink by a fraction of a percent --
        # so ask for the count as well, and step the correction down until the
        # glyph survives it.  Two thirds of the offset on a whole glyph beats
        # all of it on a torn one.
        def probe(f, rec=rec, name=name, base_area=base_area, keep=keep):
            if abs(global_delta * f) < 0.2:
                return None
            mark = len(shapes.failures)
            candidate, ok = shapes.dilate_checked(rec, global_delta * f, name)
            if not ok:
                del shapes.failures[mark:]
                return None
            settled = shapes.remove_overlap(candidate, name)
            del shapes.failures[mark:]
            settled_area = abs(shapes.area(settled))
            # Boolean operations can succeed syntactically while returning a
            # hollow or flooded glyph.  The low-level reshaper already checks
            # this; repeat it after overlap removal, a separate operation.
            if (base_area > 1.0 and
                    not (base_area * (1.0 - stem_window) <= settled_area <=
                         base_area * (1.0 + stem_window))):
                return None
            if shapes._contours(settled) != keep:
                return None
            return settled

        accepted, took = settle_largest(probe)
        if accepted is None:
            out[name] = base
            guarded += 1
            guarded_names.append(name)
            residual.append(abs(global_delta))
            continue
        out[name] = accepted
        residual.append(abs(global_delta) * (1.0 - took))
        if took == 1.0:
            full += 1
        else:
            partial += 1

    # Noto's horizontal/vertical ratio is not carried by the wght axis, so keep
    # the existing class-wide bar correction.
    ratio_values = []
    bar_values = []
    for ch in KANJI_BAR_SAMPLE:
        name = cmap.get(ord(ch))
        rec = out.get(name) if name else None
        if not rec:
            continue
        stem = shapes.stem_of(rec, cuts=shapes.CJK_CUTS)
        bar = shapes.cjk_bar_of(rec)
        if stem and bar:
            ratio_values.append(bar / stem)
            bar_values.append(bar)
    want_kanji_bar = _at(HIRAGINO_BAR_OVER_STEM, target_stem)
    have_kanji_bar = statistics.median(ratio_values)
    kanji_bar_delta = 0.0
    kanji_bars_changed = kanji_bars_rejected = 0
    if abs(have_kanji_bar - want_kanji_bar) > 0.04:
        final_kanji_stem = median_stem(
            out, cmap, KANJI_SAMPLE, shapes.CJK_CUTS)
        kanji_bar_delta = (final_kanji_stem * want_kanji_bar -
                           statistics.median(bar_values))
        bar_window = area_window(kanji_bar_delta, final_kanji_stem)
        kanji_names = {
            name for cp, name in cmap.items()
            if ((0x3400 <= cp <= 0x9FFF) or (0xF900 <= cp <= 0xFAFF))
        }
        for name in kanji_names:
            rec = out.get(name)
            if not rec:
                continue
            base = shapes.remove_overlap(rec, name)
            base_area = abs(shapes.area(base))
            keep = shapes._contours(base)
            # Same rule as the stem pass above: a bar erosion that changes the
            # count severed or flooded something, whatever the area says.
            def probe(f, rec=rec, name=name, base_area=base_area, keep=keep):
                mark = len(shapes.failures)
                candidate, ok = shapes.adjust_bars_checked(
                    rec, kanji_bar_delta * f, tag=name)
                if not ok:
                    del shapes.failures[mark:]
                    return None
                settled = shapes.remove_overlap(candidate, name)
                del shapes.failures[mark:]
                settled_area = abs(shapes.area(settled))
                if (base_area > 1.0 and
                        not (base_area * (1.0 - bar_window) <= settled_area <=
                             base_area * (1.0 + bar_window))):
                    return None
                if shapes._contours(settled) != keep:
                    return None
                return settled

            settled, took = settle_largest(probe)
            if settled is None:
                kanji_bars_rejected += 1
            else:
                out[name] = settled
                kanji_bars_changed += 1

    # Kana already come from their own solved wght locations.  The residual
    # path below is retained only for sub-unit misses after uniform sizing.
    kana_correction = {}
    for tag, cp_range, stem_sample, stem_model, bar_model in (
            ("hira", HIRAGANA, HIRA_BAR_SAMPLE,
             HIRAGINO_HIRA_STEM, HIRAGINO_HIRA_BAR),
            ("kata", KATAKANA, KATA_BAR_SAMPLE,
             HIRAGINO_KATA_STEM, HIRAGINO_KATA_BAR)):
        have_stem = median_stem(out, cmap, stem_sample, shapes.CJK_CUTS)
        want_stem = target_stem * _at(stem_model, target_stem)
        stem_delta = want_stem - have_stem
        want_bar = _at(bar_model, target_stem)
        changed = bar_changed = rejected = bar_stem_reverts = 0
        names = {cmap[cp] for cp in cp_range if cp in cmap}
        # The bar target is Hiragino's *class* median, and forcing every kana
        # onto it one by one read whatever a vertical cut crosses as a bar --
        # the diagonal of `ル`, the curve of `し` -- and thinned those by up to
        # 13 % against their Noto source (ル レ し り に じ) while `あ` and
        # `す` grew 8-10 %.  Bar/stem is a per-character design ratio (っ 0.68,
        # い 2.03 in Noto); the class median says nothing about one glyph.
        # Moving the whole class by its median miss was tried too and is
        # worse: half the katakana take it and half are refused.  So kana keep
        # Noto's own bars at their solved wght.  Off since Friday Sans 1.0;
        # Friday Mono v47/v48 shipped with the per-glyph pass.
        KANA_BAR_MATCH = KANA_BAR_MATCH_DEFAULT
        for name in names:
            rec = out.get(name)
            if not rec:
                continue
            base = shapes.remove_overlap(rec, name)
            keep = shapes._contours(base)
            base_area = abs(shapes.area(base))
            best = base
            # The kanji passes bound the area a correction may move; this one
            # did not, so a dilation that floods a small kana's counter shut
            # was held back by the contour count alone -- and the count of
            # `ぉ` never moves, at any fraction of the offset.  Same window,
            # same reason.
            kana_window = area_window(stem_delta, want_stem)
            if abs(stem_delta) > 0.25:
                candidate, took = shapes.dilate_graded(
                    rec, stem_delta, name, steps=(1.0, 0.66, 0.33))
                settled = shapes.remove_overlap(candidate, name)
                if (took and shapes._contours(settled) == keep and
                        in_area_window(settled, base_area, kana_window)):
                    best = settled
                    changed += 1
                elif took:
                    rejected += 1
            stem = shapes.stem_of(best, cuts=shapes.CJK_CUTS)
            bar = shapes.cjk_bar_of(best)
            if stem and bar and KANA_BAR_MATCH:
                bar_delta = stem * want_bar - bar
                if abs(bar_delta) > 0.8:
                    candidate, took = shapes.adjust_bars_graded(
                        best, bar_delta, tag=name)
                    settled = shapes.remove_overlap(candidate, name)
                    # `adjust_bars` promises to change horizontal bars and
                    # leave vertical stems alone.  On a kana with no bar at all
                    # it cannot keep that promise: `cjk_bar_of` reads a curve as
                    # a bar and returns nonsense -- い measured bar/stem 1.93,
                    # ん 1.55 -- so the correction chased a target 60 % away and
                    # took the near-vertical strokes down with it.  い and ん
                    # shipped 25 % thinner than the rest of the kana, え, る and
                    # ろ 20-30 % thicker.  Hold the operation to its contract:
                    # if the stem moved, the bar reading was not a bar.
                    kept_stem = (shapes.stem_of(settled, cuts=shapes.CJK_CUTS)
                                 if took else None)
                    moved = (kept_stem is None or
                             abs(kept_stem - stem) > max(0.02 * stem, 0.4))
                    if (took and not moved and
                            shapes._contours(settled) == keep and
                            in_area_window(settled, base_area,
                                           area_window(bar_delta, stem))):
                        best = settled
                        bar_changed += 1
                    elif took:
                        rejected += 1
                        if moved:
                            bar_stem_reverts += 1
            out[name] = best
        kana_correction[tag] = {
            "stem_delta": round(stem_delta, 2),
            "stem_changed": changed,
            "bar_changed": bar_changed,
            "rejected": rejected,
            "no_bar": bar_stem_reverts,
        }

    # Both kana classes sit a little lower than Hiragino.  A pure translation
    # fixes the optical phase without changing a curve or stroke weight.
    kana_lift = {}
    lifted_names = set()
    lift_shift = {}
    for tag, chars, rise_model in (
            ("hira", HIRA_SAMPLE_FULL, HIRAGINO_HIRA_RISE),
            ("kata", KATA_SAMPLE_FULL, HIRAGINO_KATA_RISE)):
        frame = frame_of(out, cmap, chars)
        desired_centre = want_centre + _at(rise_model, target_stem) * CJK_SCALE
        lift = desired_centre - frame[2]
        kana_lift[tag] = round(lift, 2)
        names = {cmap[ord(ch)] for ch in chars if ord(ch) in cmap}
        # Include small, voiced and half-width kana in the same class.
        cp_range = HIRAGANA if tag == "hira" else KATAKANA
        names.update(cmap[cp] for cp in cp_range if cp in cmap)
        shift = Transform(1, 0, 0, 1, 0, lift)
        for name in names:
            if name in out and out[name]:
                out[name] = shapes.transform(out[name], shift)
                lifted_names.add(name)
                lift_shift[name] = shift

    # The class lift above moves both syllabaries as a block and leaves the
    # scatter inside each one exactly as Noto drew it.  This is where the
    # family earns the fixed cell: settle each kana individually.
    rhythm = kana_rhythm(out, cmap)
    for name, dy in rhythm.items():
        if not out.get(name):
            continue
        out[name] = shapes.transform(out[name], Transform(1, 0, 0, 1, 0, dy))
        lifted_names.add(name)
        # Fold the nudge into the shift the guards below correct their
        # reference by.  Leaving it out is the v3.3 `ぉ` bug in a new place:
        # the reference would sit a few units off and every kana would read as
        # damaged, or worse, the threshold would be widened until nothing did.
        prior = lift_shift.get(name, Transform(1, 0, 0, 1, 0, 0))
        lift_shift[name] = Transform(1, 0, 0, 1, 0, prior[5] + dy)
    kana_lift["rhythm"] = "%d 字 / 平均 %.1fu / 最大 %.1fu" % (
        len(rhythm),
        statistics.mean(abs(d) for d in rhythm.values()) if rhythm else 0.0,
        max((abs(d) for d in rhythm.values()), default=0.0))

    # The guards below all ask "how far has this glyph drifted from the sound
    # source it started as", and the answer is only meaningful if the source
    # they compare against sits where the finished glyph sits.  A lifted kana
    # does not, which is why v3.3 excluded kana from the ink guard outright --
    # and shipped Medium's `ぉ` and `ゥ` flooded solid, with the contour
    # count unchanged from the source at every step, so nothing saw them.  The
    # lift is a pure translation of a known amount, so move the reference by
    # the same amount instead of dropping the check.  Reverting to `source_ref`
    # rather than to `scaled` also keeps a reverted kana at its corrected
    # optical height; reverting to `scaled` silently undid the lift.
    source_ref = dict(scaled)
    for name, shift in lift_shift.items():
        if scaled.get(name):
            source_ref[name] = shapes.transform(scaled[name], shift)


    # ---------------------------------------------------------------- guards
    #
    # Everything above is a boolean operation on an outline, and skia can
    # succeed on all of them and still hand back a glyph a reader would call
    # broken.  Both checks below measure the finished glyph against the one
    # thing known to be sound -- the plain scaled source in `scaled` -- and
    # where they disagree the source wins.  Neither is a correction; they only
    # undo damage.

    # Pitfall 3(a) again: the anisotropic passes leave hairs.  `prune`'s floor
    # of 100 square units was set from the hairs the erosion leaves; the ones
    # the bar pass leaves are bigger -- 万 shipped a 126-unit hair beside a
    # 189,000-unit stroke, 動 a 1,484-unit one, and 3,211 kanji (a quarter of
    # the repertoire) carried at least one.  They are invisible as shapes and
    # visible as noise: extra contours for the hinter to snap, and a smudge at
    # 13 px.  A hair is a rounding error against the glyph it sits in, so
    # measure it that way rather than against a fixed number, and keep the
    # absolute ceiling low enough that the smallest real mark in the font --
    # a hiragana dakuten at 6,600 units -- cannot be caught by it.
    # Size alone is not enough to tell a hair from a mark.  Eighty-one
    # characters in the source -- 爨, 獻, 纜, 灋 and their kind, where a stroke
    # closes a counter no bigger than a full stop -- draw a contour that is
    # both under two percent of the glyph and under 4,000 units, and a rule
    # written on those two numbers alone deletes them.  So ask the source how
    # many contours the character has and remove only the surplus: a hair is
    # by definition a contour that was not there before.  Smallest first, so
    # the surplus that goes is the surplus least likely to be a stroke.
    spurs = 0
    for name, rec in out.items():
        if not rec:
            continue
        parts = shapes.contours(rec)
        if len(parts) < 2:
            continue
        areas = [abs(shapes.area(c)) for c in parts]
        total = sum(areas)
        if total <= 0.0:
            continue
        cand = sorted((a, i) for i, a in enumerate(areas)
                      if a < 0.02 * total and a < SPUR_AREA)
        base = scaled.get(name)
        if not cand or not base:
            continue
        surplus = len(parts) - shapes._contours(shapes.remove_overlap(base, name))
        if surplus <= 0:
            continue
        drop = {i for _, i in cand[:surplus]}
        out[name] = [op for i, c in enumerate(parts) if i not in drop for op in c]
        spurs += 1

    # v3.3 backstop.  Every pass above now refuses an edit that changes the
    # contour count, but the passes run in sequence and each one measures
    # against the glyph it was handed, not against the source.  Measure the
    # finished glyph against the scaled source once, and where the topology
    # still differs take the source: whatever produced the difference, no
    # correction in this build is worth a torn or flooded character.  This is
    # the check `validate.py` repeats on the written file.
    reverted_topo = []
    for name, rec in out.items():
        base = source_ref.get(name)
        if not rec or not base:
            continue
        settled_base = shapes.remove_overlap(base, name)
        if shapes._contours(rec) != shapes._contours(settled_base):
            out[name] = settled_base
            reverted_topo.append(name)

    # A glyph that lost a stroke or filled a counter shows up as ink that no
    # longer matches the source's.  The reshape thins every glyph by the same
    # offset, so the whole font's ink moves together and it is the *outliers*
    # that are damage: 枠 came back at 0.72 of the shared ratio with its right
    # half gone, 踧 at 0.75 reduced to 叔, 灸 at 1.28 with its foot flooded
    # solid.  Thirty-seven characters were destroyed this way.  None was a
    # 常用漢字, which is why nothing caught them.
    ratios = {}
    for name, rec in out.items():
        base = source_ref.get(name)
        if not rec or not base:
            continue
        a, b = abs(shapes.area(rec)), abs(shapes.area(base))
        if b > 1.0:
            ratios[name] = a / b
    # Three things can be wrong with a finished glyph, and none of them is
    # visible to the other two.
    #
    #   ink ratio  the glyph as a whole holds too much or too little ink --
    #              枠 came back at 0.72 of the shared ratio with its right half
    #              gone, 灸 at 1.28 with its foot flooded solid.
    #   iou        the glyph no longer looks like the character -- 追 shipped
    #              with its walking radical destroyed and its 白 flooded, and
    #              its ink was within a percent of everything else because the
    #              flood paid for what the counter lost.
    #   excess     one part of the glyph is solid black while the rest is
    #              right.  A flood between two strokes closes no counter, so
    #              the count is right; it fills a few percent of the glyph, so
    #              the ink total is right; and it survives the iou floor,
    #              because most of the character is still there.  談 薬 鶏 遮
    #              坐 -- five 常用漢字 -- all shipped this way.  Only a local
    #              measure sees it.
    #
    # The remedy is the same question the stem pass asks, not a revert.  v3.2
    # reverted an outlier outright, and a reverted glyph carries the source
    # stem, 9.8 % heavier than the rest of the face at Regular; that put a
    # visible patch of another weight into running text for 847 characters to
    # fix damage that a smaller offset would have avoided entirely.  So bisect
    # the offset for the largest share this glyph survives on all three
    # measures at once, and go back to the source only for what fails at every
    # level.
    damaged = []
    excess_ceiling = 1.0
    if ratios:
        shared = statistics.median(ratios.values())
        lo_r = shared * (1.0 - INK_TOLERANCE)
        hi_r = shared * (1.0 + INK_TOLERANCE)
        measured = {}
        for name, rec in sorted(out.items()):
            src = source_ref.get(name)
            if not rec or not src:
                continue
            measured[name] = shapes.ink_compare(rec, src)

        # The excess ceiling cannot be a constant, and a constant is what the
        # first version of this used.  Where the correction is an erosion the
        # finished glyph adds ink nowhere, so the honest population sits at
        # nothing (Regular: median 0.016) and 0.20 is a wide margin.  Where it
        # is a dilation every stroke grows, so every glyph adds ink everywhere
        # and the honest population moves with it (Bold, +9.44: median 0.172,
        # and 孯 禮 慳 撦 鏆 櫺 遵 偃 reach 0.38-0.50 with nothing wrong with
        # them).  A ceiling of 0.20 called seven thousand sound Bold glyphs
        # damaged and cost the face three percent of its stem repairing them.
        # So take the ceiling from the face's own distribution, the way the
        # ink ratio already takes its centre: the median is the uniform growth
        # this weight asked for, the spread up to the ninth decile is how much
        # of it an ordinary glyph varies by, and damage is far outside both.
        vals = sorted(e for _, e in measured.values() if e is not None)
        if vals:
            mid = vals[len(vals) // 2]
            p90 = vals[min(len(vals) - 1, int(0.90 * (len(vals) - 1)))]
            excess_ceiling = min(
                mid + EXCESS_SPREADS * max(p90 - mid, 0.004), EXCESS_ABSOLUTE)
        for name, (iou, excess) in measured.items():
            r = ratios.get(name)
            if ((r is not None and not (lo_r <= r <= hi_r)) or
                    (iou is not None and iou < SHAPE_FLOOR) or
                    (excess is not None and excess > excess_ceiling)):
                damaged.append(name)

    reverted_damage = []
    repaired_damage = []
    for name in damaged:
        src = source_ref[name]
        src_area = abs(shapes.area(src))
        base = shapes.remove_overlap(src, name)
        base_area = abs(shapes.area(base))
        keep = shapes._contours(base)

        def probe(f, src=src, name=name, src_area=src_area,
                  base_area=base_area, keep=keep):
            if abs(global_delta * f) < 0.2:
                return None
            mark = len(shapes.failures)
            cand, ok = shapes.dilate_checked(src, global_delta * f, name)
            if not ok:
                del shapes.failures[mark:]
                return None
            settled = shapes.remove_overlap(cand, name)
            del shapes.failures[mark:]
            area = abs(shapes.area(settled))
            if (base_area > 1.0 and
                    not (base_area * (1.0 - stem_window) <= area <=
                         base_area * (1.0 + stem_window))):
                return None
            if shapes._contours(settled) != keep:
                return None
            if src_area > 1.0 and not (lo_r <= area / src_area <= hi_r):
                return None
            iou, excess = shapes.ink_compare(settled, src)
            if iou is not None and iou < SHAPE_FLOOR:
                return None
            if excess is not None and excess > excess_ceiling:
                return None
            return settled

        best, took = settle_largest(probe)
        if best is None:
            out[name] = base
            reverted_damage.append(name)
        else:
            out[name] = best
            repaired_damage.append(took)

    redrawn, redraw_missed = hand_redraw(out, cmap, style)
    trimmed = trim_stubs(out, cmap)

    final_frame = frame_of(out, cmap, FRAME_SAMPLE)
    final_stem = median_stem(out, cmap, KANJI_SAMPLE, shapes.CJK_CUTS)
    report = dict(
        source=os.path.basename(NOTO_CJK),
        source_wght={"kanji": round(kanji_wght, 2),
                     "hira": round(hira_wght, 2),
                     "kata": round(kata_wght, 2)},
        source_upem=source_upem,
        scale=round(scale, 4),
        frame="%.0fx%.0f -> %.0fx%.0f" %
              (src_w, src_h, final_frame[0], final_frame[1]),
        target_frame="%.0fx%.0f" % (target_w, target_h),
        source_stem=round(src_stem, 2),
        cells="full %d / half %d (%d refitted)" %
              (sum(1 for v in cell_of.values() if v == CJK_ADV),
               sum(1 for v in cell_of.values() if v == LATIN_ADV), refitted),
        global_delta=round(global_delta, 2),
        final_stem=round(final_stem, 2),
        reshape="full %d / partial %d / unchanged %d / guarded %d "
                "(stem residual mean %.2f / max %.2f of %.2f)" %
                (full, partial, unchanged, guarded,
                 (sum(residual) / len(residual)) if residual else 0.0,
                 max(residual) if residual else 0.0, abs(global_delta)),
        kanji_bar="delta %.2f / changed %d / rejected %d" %
                  (kanji_bar_delta, kanji_bars_changed, kanji_bars_rejected),
        kana="weight %s; lift %s" % (kana_correction, kana_lift),
        guards="spurs removed %d / topology reverted %d / damaged %d "
               "(excess ceiling %.3f) -> repaired %d (took %s) reverted %d %s" %
               (spurs, len(reverted_topo), len(damaged), excess_ceiling,
                len(repaired_damage),
                " ".join("%.2f" % q for q in _quantiles(repaired_damage)),
                len(reverted_damage), reverted_damage[:12]),
        trimmed="".join(trimmed) or "-",
        hand_drawn="".join(redrawn) + (
            " (入らず: %s)" % ", ".join(redraw_missed)
            if redraw_missed else ""),
        guarded_names=sorted(guarded_names)[:24],
    )
    return out, cmap, cell_of, vert, report


def to_glyf(rec, glyph_set_names=None):
    pen = TTGlyphPen(None)
    for op, args in rec:
        if op == "addComponent":
            continue
        getattr(pen, op)(*args)
    return pen.glyph()


def notdef_glyph():
    """A hollow box, the way every shipping font draws it.

    v3.0 emitted an empty .notdef, which makes a character the font does not
    have indistinguishable from a space -- exactly the case where the reader
    most needs to be told that something is missing.
    """
    pen = TTGlyphPen(None)
    for box, reverse in (((110, 0, 490, 700), False), ((160, 50, 440, 650), True)):
        x0, y0, x1, y1 = box
        pts = [(x0, y0), (x0, y1), (x1, y1), (x1, y0)]
        if reverse:
            pts.reverse()
        pen.moveTo(pts[0])
        for pt in pts[1:]:
            pen.lineTo(pt)
        pen.closePath()
    return pen.glyph()


# Windows reads the OS/2 code-page bits to decide what a font is *for*.  A face
# that declares none is one no legacy charset claims, and parts of the shell --
# the font preview among them -- lay it out as though it covered nothing.  v3.0
# left the field at zero.  Each entry is a bit and the characters that must all
# be present for the claim to be true.
CODEPAGES = [
    (0,  "\u00c0\u00df\u00ff"),         # 1252 Latin 1
    (1,  "\u0102\u0139\u017b"),         # 1250 Latin 2, Central Europe
    (2,  "\u0410\u042f\u0451"),         # 1251 Cyrillic
    (3,  "\u0391\u03c9"),                # 1253 Greek
    (4,  "\u011e\u0130\u015e"),         # 1254 Turkish
    (7,  "\u0104\u0172\u016a"),         # 1257 Windows Baltic
    (17, "\u3042\u30a2\u4e00\uff21"),  # 932 JIS / Japan
    (29, "\u00c0"),                       # Macintosh character set
    (30, "\u00c0"),                       # OEM character set
]


def codepage_bits(cmap):
    bits = 0
    for bit, need in CODEPAGES:
        if all(ord(c) in cmap for c in need):
            bits |= 1 << bit
    return bits


def _quantiles(values, points=(0.0, 0.1, 0.5, 0.9, 1.0)):
    """Min / 10th / median / 90th / max of a sample, for the build report."""
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return []
    return [vals[min(len(vals) - 1, int(round(q * (len(vals) - 1))))]
            for q in points]


def write_build_targets(out_dir, args):
    """Record what this build actually ran with, next to the fonts.

    `validate.py` re-derives its targets by importing this module and reading
    its globals, which makes the two agree by construction -- and agree just as
    happily when the build ran with `--widen 1.2` and the check ran with the
    default.  The formulas are the specification and stay shared; the
    *parameters* are a property of one build and have to travel with its
    output.  A face whose sidecar is missing or disagrees is a face nobody has
    checked, and `validate.py` now says so instead of printing OK.
    """
    with open(os.path.join(DRAWINGS, "vector-masters.json"), "rb") as master_file:
        master_hash = hashlib.sha256(master_file.read()).hexdigest()
    path = os.path.join(out_dir, "build-targets.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({
            "version": VERSION,
            "revision": REVISION,
            "cell": CELL_LATIN,
            "widen": LATIN_WIDEN,
            "cjk_scale": CJK_SCALE,
            "cjk_source": os.path.basename(NOTO_CJK),
            "settle_ladder": list(SETTLE_LADDER),
            "kana_rhythm_gain": KANA_RHYTHM_GAIN,
            "hand_master": "common-skeleton-2",
            "hand_master_sha256": master_hash,
            "ink_tolerance": INK_TOLERANCE,
            "shape_floor": SHAPE_FLOOR,
            "excess_spreads": EXCESS_SPREADS,
        }, fh, indent=2, sort_keys=True)
    return path


def in_area_window(rec, base_area, window):
    """True when `rec` holds an area `base_area` could honestly have become."""
    if base_area <= 1.0:
        return True
    a = abs(shapes.area(rec))
    return base_area * (1.0 - window) <= a <= base_area * (1.0 + window)


def area_window(amount, stem):
    """Fractional area change a correction of `amount` can honestly produce.

    v3.3 used a fixed 0.55-1.55 window at every call site.  A window that
    wide is not a guard: `global_delta` is under ten units on a 900-unit
    frame, where the honest area change is a few percent, so +/-55 % passes a
    glyph whose counters have all flooded solid as readily as a sound one.

    Dilating a stroke of width `w` by `d` takes it to `w + d`, so the
    fractional area change of a whole glyph is about `|d| / stem`.  Allow
    three times that -- a glyph is not one stroke, and the terminals grow in
    two directions -- with a floor for the corrections small enough that the
    ratio underflows, and a ceiling so this can never be looser than what it
    replaced.
    """
    frac = 3.0 * abs(amount) / max(stem, 1.0)
    return max(0.08, min(0.45, frac))


def settle_largest(probe, ladder=SETTLE_LADDER):
    """Largest fraction of a correction a glyph survives.

    The passes below all ask the same question -- how much of this offset can
    this outline take before the boolean solver tears or floods it -- and the
    honest answer is a number between nothing and everything.  v3.2 sampled it
    at three points (1, 2/3, 1/3), which was enough while the only test was a
    coarse area window.  With the contour count in the test the ladder is no
    longer good enough: a glyph that fails at 1/3 fell all the way to zero
    correction, and zero means the source stem, which at Regular is 9.8 %
    heavier than the rest of the face -- a visible patch of another weight in
    the middle of running text, which is exactly what a repair must not leave
    behind.

    v3.3 bisected instead, on the stated reasoning that "damage is monotonic
    in the offset -- a wider erosion cannot re-open a counter it has already
    closed".  That is true of a counter and false of the test actually used.
    The test is `_contours(settled) == keep`, an *equality*, and the contour
    count is not monotonic in the offset: `shapes._tore` documents an erosion
    both raising the count (a stroke severed) and lowering it (two counters
    run together), and a wider erosion can consume the hairline a narrower one
    merely split, putting the count back.  An equality over a non-monotone
    quantity has no reason to admit an interval, and bisection assumes the
    accepted set is the interval [0, t].  It returned *an* accepted fraction,
    never provably the largest, and reported it as the largest.

    So walk a fixed ladder from the top down and take the first fraction that
    passes.  No monotonicity is assumed, the result is deterministic, and the
    worst case is one probe per rung instead of an unbounded promise.  The
    rungs are 1/8 apart, which at Regular's 6.8-unit offset is 0.85 units;
    finer than that is below the rounding at the end of the build.

    `probe(f)` returns the settled outline for that fraction, or None.
    """
    for f in ladder:
        got = probe(f)
        if got is not None:
            return got, f
    return None, 0.0


def feature_code(plain, vert):
    """The GSUB this face carries, as feature-file source.

    Monospaced text needs no kerning and wants no ligatures, so there is no
    GPOS and no `liga`.  What it does need is a way to ask for the other zero,
    and the vertical forms the CJK source already draws -- the brackets and
    punctuation that have to turn ninety degrees when the text does.
    """
    lines = ["languagesystem DFLT dflt;", "languagesystem latn dflt;",
             "languagesystem kana dflt;"]
    # `ss01` means the same thing in both families: give me the other zero.  In
    # the plain family that other zero is the slashed one, which is what the
    # standard `zero` feature is defined to produce, so it is offered under
    # that name as well.
    lines.append("feature ss01 { sub zero by zero.alt; } ss01;")
    lines.append("feature cv01 { sub zero by zero.alt; } cv01;")
    if plain:
        lines.append("feature zero { sub zero by zero.alt; } zero;")
    if vert:
        body = "".join("    sub %s by %s;\n" % (a, b) for a, b in sorted(vert.items()))
        for tag in ("vert", "vrt2"):
            lines.append("feature %s {\n%s} %s;" % (tag, body, tag))
    return "\n".join(lines) + "\n"


def assemble(style, weight, italic, latin, latin_cmap, cjk, cjk_cmap,
             cjk_adv, cjk_vert, out_path, plain=False):
    order = [".notdef"]
    glyphs = {".notdef": notdef_glyph()}
    metrics = {".notdef": (CELL_LATIN, 60)}
    cmap_out = {}
    boxes = {}

    def add(name, rec, adv, cell=None):
        # `adv` is the design cell; CELL_* is the cell the face advances by.
        # They come apart for the wide symbols Iosevka draws and the CJK
        # source does not: those stay the size they were drawn and are
        # centred in the two-column cell Unicode gives them.
        if cell is None:
            cell = 0 if adv == 0 else (CELL_LATIN if adv == LATIN_ADV else CELL_CJK)
        shift = (cell - adv) / 2.0 if cell else 0
        if shift:
            rec = shapes.translate(rec, shift)
        order.append(name)
        glyphs[name] = to_glyf(rec)
        b = shapes.bbox(rec)
        boxes[name] = b
        metrics[name] = (cell, int(round(b[0])) if b else 0)

    def fit_cell(rec, cell):
        """Keep a proportional-source glyph inside its assigned grid cell."""
        box = shapes.bbox(rec)
        if not box or (box[0] >= 0 and box[2] <= cell):
            return rec
        width = box[2] - box[0]
        if width > cell:
            g = cell / width
            cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
            rec = shapes.scale_about(rec, g, 1.0, cx, cy)
            box = shapes.bbox(rec)
        return shapes.translate(rec, cell / 2.0 - (box[0] + box[2]) / 2.0)

    # The two zeros come from matching Iosevka build plans and have both passed
    # through the same transforms in build_latin.
    slashed = latin.get(latin_cmap[ord("0")])
    unslashed = latin.get("zero.unslashed")
    zero_default = (unslashed if plain else slashed) or slashed
    zero_other = (slashed if plain else unslashed)

    for cp, name in sorted(latin_cmap.items()):
        if name not in latin or is_cjk_cp(cp):
            continue
        # Unicode calls 77 of the symbols Iosevka draws two columns wide, and
        # the terminal will allot two.  Thirteen of them the CJK source draws
        # as well: leave those to it, below, and they come out full size.  The
        # other 64 -- ⌚ ⏰ ⚡ ⭐ and their neighbours -- exist nowhere else, so
        # keep Iosevka's drawing and give it the cell Unicode asks for.
        wide = is_fullwidth_cp(cp)
        if (wide or is_symbol_from_cjk(cp)) and cjk_cmap.get(cp) in cjk:
            continue
        cell = 0 if zero_advance(cp) else (CELL_CJK if wide else CELL_LATIN)
        rec = zero_default if cp == 0x30 else latin[name]
        if unicodedata.category(chr(cp)) == "Cf" or cp == 0x034F:
            rec = []
        out_name = name
        if out_name in glyphs and metrics[out_name][0] != cell:
            out_name = "%s.%04X" % (name, cp)
        if out_name not in glyphs:
            add(out_name, rec, LATIN_ADV, cell=cell)
        cmap_out[cp] = out_name
    if zero_other:
        add("zero.alt", zero_other, LATIN_ADV)

    jp_of = {}
    for cp, name in sorted(cjk_cmap.items()):
        if cp in cmap_out or name not in cjk:
            continue
        jn = "jp." + name
        adv = 0 if zero_advance(cp) else (CJK_ADV if is_fullwidth_cp(cp) else LATIN_ADV)
        if jn in glyphs and metrics[jn][0] != adv:
            jn = "%s.%04X" % (jn, cp)
        if jn not in glyphs:
            rec = cjk[name]
            if adv and not 0x2500 <= cp <= 0x259F:
                rec = fit_cell(rec, adv)
            add(jn, rec, adv)
        jp_of[name] = jn
        cmap_out[cp] = jn

    # The vertical forms are not in the character map -- they exist only as the
    # target of a `vert` substitution -- so they have to be carried across by
    # name, or the feature would point at nothing.
    vert_out = {}
    for src, dst in sorted(cjk_vert.items()):
        if src not in jp_of or dst not in cjk:
            continue
        jn = "jp." + dst
        if jn not in glyphs:
            add(jn, cjk[dst], cjk_adv.get(dst, metrics[jp_of[src]][0]))
        vert_out[jp_of[src]] = jn

    uvs_out = {}
    for selector, pairs in release_uvs().items():
        kept = []
        for cp, dst in pairs:
            if cp not in cmap_out:
                continue
            if dst is None:
                kept.append((cp, None))
            elif dst in cjk:
                jn = "jp." + dst
                if jn not in glyphs:
                    add(jn, cjk[dst], CJK_ADV)
                kept.append((cp, jn))
        if kept:
            uvs_out[selector] = kept

    # Windows clips to the usWin box.  v3.0 read it off the first four hundred
    # glyphs of each side and shipped a descent of 268 against real ink at
    # -385, which cut the bottom off every glyph that reached past it.
    tops = [b[3] for b in boxes.values() if b]
    bottoms = [b[1] for b in boxes.values() if b]
    win_asc = int(math.ceil(max(tops))) if tops else 900
    win_desc = int(math.ceil(-min(bottoms))) if bottoms else 250

    family = FAMILY + (" Plain" if plain else "")
    fb = FontBuilder(UPEM, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap_out)
    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
    uv = CmapSubtable.newSubtable(14)
    uv.platformID, uv.platEncID, uv.language = 0, 5, 0
    uv.cmap, uv.uvsDict = {}, uvs_out
    fb.font["cmap"].tables.append(uv)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)

    # RIBBI: only Regular, Italic, Bold and Bold Italic may share a family
    # name.  Medium is none of those, so it ships as its own family and its
    # own subfamily is Regular or Italic -- which is also why the REGULAR bit
    # below follows the subfamily and not the weight.
    subfamily = ("%s Italic" % style if italic else style) if style != "Regular" \
        else ("Italic" if italic else "Regular")
    full = "%s %s" % (family, subfamily)
    ps = "%s-%s" % (family.replace(" ", ""), subfamily.replace(" ", ""))
    rtl = subfamily in ("Regular", "Italic", "Bold", "Bold Italic")
    fb.setupNameTable({
        "familyName": family if rtl else "%s %s" % (family, style),
        "styleName": subfamily if rtl else ("Italic" if italic else "Regular"),
        "uniqueFontIdentifier": "%s;%s;%s" % (VERSION, VENDOR, ps),
        "fullName": full,
        "psName": ps,
        "version": VERSION,
        "copyright": COPYRIGHT,
        "description": DESCRIPTION,
        "licenseDescription": LICENSE,
        "licenseInfoURL": LICENSE_URL,
        "typographicFamily": family,
        "typographicSubfamily": subfamily,
        "manufacturer": MANUFACTURER,
        "designer": MANUFACTURER,
        "sampleText": SAMPLE_TEXT,
    })
    def ink_top(ch, fallback):
        name = cmap_out.get(ord(ch))
        b = boxes.get(name) if name else None
        return int(round(b[3])) if b else fallback

    cap_height_ink = ink_top("H", 710)
    x_height_ink = ink_top("x", 530)

    fb.setupHorizontalHeader(ascent=int(UPEM * 0.88), descent=-int(UPEM * 0.12),
                             lineGap=0)
    fb.setupOS2(
        version=4,
        sTypoAscender=int(UPEM * 0.88), sTypoDescender=-int(UPEM * 0.12),
        sTypoLineGap=0,
        usWinAscent=win_asc, usWinDescent=win_desc,
        usWeightClass=weight, usWidthClass=5,
        # The bar correction erodes amount/2 off every flat top and bottom, so
        # the drawn cap is not the 710 the plan asked for and the drawn x-height
        # is not 530.  Report what the outlines actually do; a hinter that snaps
        # to a declared height the ink never reaches blurs the very stems it is
        # there to sharpen.
        sxHeight=x_height_ink, sCapHeight=cap_height_ink,
        achVendID=VENDOR, fsType=0,
        # The average character width of a Japanese monospace is its *Latin*
        # advance, not the mean over a glyph set that is seven-eighths CJK: MS
        # Gothic and BIZ UDGothic both report the half-width cell.  v3.0
        # reported 942, and every Windows control that sizes itself from
        # tmAveCharWidth laid the face out nearly twice too wide.
        xAvgCharWidth=CELL_LATIN,
        ulCodePageRange1=codepage_bits(cmap_out), ulCodePageRange2=0,
        ySubscriptXSize=650, ySubscriptYSize=600,
        ySubscriptXOffset=0, ySubscriptYOffset=75,
        ySuperscriptXSize=650, ySuperscriptYSize=600,
        ySuperscriptXOffset=0, ySuperscriptYOffset=350,
        yStrikeoutSize=int(round(SF[style][1])),
        yStrikeoutPosition=265,
        # usWinAscent/Descent is the Windows *clipping* box and has to cover
        # the tallest composite in the font -- here 1138/389, 1.53 em.  Left to
        # itself GDI would also line-space from it, opening the terminal to
        # half again the leading the typo metrics ask for.  Bit 7 says: clip by
        # usWin, lead by sTypo.  Without it the same file sets line height
        # 1.53 on Windows and 1.00 everywhere else.
        #
        # Bit 6 is REGULAR and it follows the *subfamily*, not the weight.
        # Medium ships as its own RIBBI family -- family "Inori Mono Medium",
        # subfamily "Regular" -- so it is a regular face and has to say so.
        # Reading the weight name here left Medium with neither bit 5 nor
        # bit 6, which is the one combination the spec does not allow.
        # Bit 0 is ITALIC and bit 6 is REGULAR; they are exclusive, and an
        # italic face is never the regular one.
        fsSelection=(1 << 0 if italic else 0)
                    | (1 << 5 if style == "Bold" else 0)
                    | (0 if (style == "Bold" or italic) else 1 << 6)
                    | (1 << 7),
        panose=dict(bFamilyType=2, bSerifStyle=11, bWeight=max(2, weight // 100 + 1),
                    bProportion=9, bContrast=2, bStrokeVariation=2, bArmStyle=2,
                    bLetterForm=2 + (1 if italic else 0), bMidline=2, bXHeight=4),
    )
    fb.setupPost(isFixedPitch=1, italicAngle=ITALIC_ANGLE if italic else 0.0,
                 underlinePosition=-120, underlineThickness=60)

    # Vertical metrics.  The advance is the full-width cell, so vhea has to
    # halve the same number: 500/-500 against a 1200 advance left a 200-unit
    # disagreement between the line the font advances by and the line it says
    # it occupies.  The vertical origin is then placed so that the CJK ink sits
    # centred in that cell rather than 68 units below its top and 322 above its
    # bottom, which is what pinning the origin to the horizontal ascender did.
    cjk_names = [n for cp, n in cmap_out.items()
                 if is_fullwidth_cp(cp) and boxes.get(n)]
    vcentre = (statistics.median((boxes[n][1] + boxes[n][3]) / 2.0
                                 for n in cjk_names)
               if cjk_names else UPEM * 0.38)
    vorigin = vcentre + CELL_CJK / 2.0
    fb.setupVerticalHeader(ascent=CELL_CJK // 2, descent=-(CELL_CJK // 2),
                           lineGap=0,
                           caretSlopeRise=0, caretSlopeRun=1, caretOffset=0,
                           reserved0=0, reserved1=0, reserved2=0, reserved3=0)
    fb.setupVerticalMetrics({
        n: (CELL_CJK, int(round(vorigin - (boxes[n][3] if boxes.get(n) else 0))))
        for n in order})

    from release_features import combining_features
    fb.addOpenTypeFeatures(feature_code(plain, vert_out) + combining_features(cmap_out, boxes, metrics))
    # hmtx lsb must match stored control-point bounds, not curve extrema.
    for n, glyph in glyphs.items():
        glyph.recalcBounds(glyphs)
        fb.font["hmtx"].metrics[n] = (metrics[n][0], getattr(glyph, "xMin", 0))
    fb.font["hhea"].caretSlopeRise = 1000
    fb.font["hhea"].caretSlopeRun = int(round(-math.tan(math.radians(ITALIC_ANGLE)) * 1000)) if italic else 0
    from fontTools.ttLib import newTable
    fb.font["gasp"] = newTable("gasp")
    fb.font["gasp"].gaspRange = {65535: 15}

    from release_features import add_jis_parentheses
    add_jis_parentheses(fb.font)
    from release_features import add_zero_uvs
    add_zero_uvs(fb.font)
    fb.font["head"].fontRevision = REVISION
    fb.font["head"].macStyle = (1 if style == "Bold" else 0) | (2 if italic else 0)
    fb.font["OS/2"].recalcUnicodeRanges(fb.font)
    fb.font.save(out_path)
    return len(order)


def main():
    global CELL_LATIN, CELL_CJK, CJK_SCALE, LATIN_WIDEN, LATIN_XS
    global KANA_RHYTHM_GAIN
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="fonts")
    ap.add_argument("--only", action="append", default=None,
                    help="build just these styles (repeatable)")
    ap.add_argument("--family", choices=("both", "main", "plain"), default="both",
                    help="Friday Mono, Friday Mono Plain, or both")
    ap.add_argument("--cell", type=int, default=LATIN_ADV,
                    help="欧文の送り幅。字形は変えずにセルだけ変える（既定 600）")
    ap.add_argument("--widen", type=float, default=1.0,
                    help="Iosevka 欧文の横倍率（既定 1.0）")
    ap.add_argument("--no-validate", action="store_true",
                    help="ビルド後に validate.py を回さない（既定は回して"
                         "その結果で終了コードを決める）")
    ap.add_argument("--cjk-scale", type=float, default=CJK_SCALE,
                    help="和文の光学字面倍率。中心とステムを維持する"
                         "（既定 1.0）")
    ap.add_argument("--upright-only", action="store_true",
                    help="斜体を作らない（正体 6 本だけ）")
    ap.add_argument("--kana-rhythm", type=float, default=KANA_RHYTHM_GAIN,
                    help="仮名の縦リズムをヒラギノの字別判断に対してどこまで"
                         "詰めるか。1.0 でヒラギノと同じ、0 で完全に均一"
                         "（既定 0.8）")
    ap.add_argument("--approved-visual-review", action="store_true",
                    help="Use only after the user approves the visual proof; required for a production build")
    ap.add_argument("--release-audit", action="store_true",
                    help="Build for an explicitly requested release repair; verify output before distribution")
    args = ap.parse_args()
    if not (args.approved_visual_review or args.release_audit):
        ap.error("Visual approval required. Show previews/texture-review first; "
                 "only after user approval pass --approved-visual-review.")
    LATIN_WIDEN = args.widen
    LATIN_XS = LATIN_WIDEN
    CELL_LATIN = args.cell
    CELL_CJK = args.cell * 2
    CJK_SCALE = args.cjk_scale
    KANA_RHYTHM_GAIN = args.kana_rhythm
    if KANA_RHYTHM_GAIN != 0.8:
        log("kana-rhythm: %.2f" % KANA_RHYTHM_GAIN)
    if CJK_SCALE != 1.0:
        log("cjk-scale: %.4f" % CJK_SCALE)
    if CELL_LATIN != LATIN_ADV:
        log("cell: Latin %d / CJK %d (drawn in %d / %d)"
            % (CELL_LATIN, CELL_CJK, LATIN_ADV, CJK_ADV))

    os.makedirs(args.out, exist_ok=True)
    log("targets: %s" % write_build_targets(args.out, args))
    families = {"both": (False, True), "main": (False,), "plain": (True,)}[args.family]

    styles = [s for s in STYLES if not args.only or s[0] in args.only]
    for style, weight in styles:
        t0 = time.time()
        sf_stem, sf_bar = SF[style]
        ideal = sf_stem * STEM_CORRECTION
        log("\n=== %s ===" % style)

        # Iosevka is static.  Its measured result, not the nominal target, is
        # what feeds the CJK relationship.
        stem_t = plan_latin(style, ideal)
        reach = stem_t / ideal
        bar_t = sf_bar * STEM_CORRECTION * reach
        # Back out to the uncondensed equivalent first: the ratio model in 4.3
        # was measured on Latin that had not been squeezed.
        jp_t = jp_stem_target(stem_t / STEM_CORRECTION)
        log("  Latin target stem %.1f bar %.1f (SF %.1f/%.1f x %.4f), "
            "字面 %.1f / %d = %.4f (SF %.4f), %s x%.4f"
            % (stem_t, bar_t, sf_stem, sf_bar, STEM_CORRECTION,
               480.0 * LATIN_XS, CELL_LATIN, 480.0 * LATIN_XS / CELL_LATIN,
               SF_INK[style], os.path.basename(IOSEVKA % style), LATIN_XS))
        if reach < 0.999:
            log("  Latin axis tops out at %.1f %% of the ideal %.1f"
                % (reach * 100, ideal))

        # Hiragino's 字面 grows with its weight, so the size the CJK is aiming
        # at is a function of the stem it is aiming at, not a constant.
        want_frame = (_at(HIRAGINO_FRAME_W, jp_t), _at(HIRAGINO_FRAME_H, jp_t))
        want_centre = _at(HIRAGINO_FRAME_C, jp_t)
        log("  CJK   target stem %.1f (ratio to Latin %.3f), frame %.0f x %.0f "
            "about y=%.0f"
            % (jp_t, jp_t / (stem_t / STEM_CORRECTION), want_frame[0],
               want_frame[1], want_centre))

        del shapes.failures[:]
        cjk, cjk_cmap, cjk_adv, cjk_vert, crep = build_cjk(
            style, jp_t, want_frame, want_centre)
        log("  CJK   %s" % crep)
        log("  CJK   %d vertical forms carried over" % len(cjk_vert))
        if shapes.failures:
            log("  CJK   %d glyph(s) skia could not reshape, left as drawn: %s"
                % (len(shapes.failures), [t for t, _ in shapes.failures[:8]]))

        faces = [False] if args.upright_only else [False, True]
        for italic in faces:
            del shapes.failures[:]
            latin, latin_cmap, lrep = build_latin(
                style, italic, (stem_t, bar_t, LATIN_XS))
            log("  Latin%s %s" % ("(it)" if italic else "    ", lrep))
            if shapes.failures:
                log("  Latin%s %d glyph(s) left as drawn: %s"
                    % ("(it)" if italic else "    ", len(shapes.failures),
                       [t for t, _ in shapes.failures[:8]]))
            if italic:
                # The shear is affine and cannot change topology; the boolean
                # solver run after it can, and did -- 撾 澟 邁 鄱 钁 lost a
                # contour and 馨 gained three, because leaning a glyph puts
                # strokes into contact that stood apart upright.  The merge
                # only exists to hand the hinter tidier outlines, and TrueType
                # fills by winding, so an unmerged outline renders identically.
                # Where merging would change the count, keep it as leaned.
                use_cjk = {}
                for n, r in cjk.items():
                    if not r:
                        use_cjk[n] = r
                        continue
                    leaned = shapes.shear(r, ITALIC_ANGLE, SF_CAP / 2)
                    settled = shapes.remove_overlap(leaned, n)
                    use_cjk[n] = (settled
                                  if shapes._contours(settled)
                                  == shapes._contours(r) else leaned)
            else:
                use_cjk = cjk
            for plain in families:
                stem_name = "FridayMonoPlain" if plain else "FridayMono"
                suffix = "Italic" if italic else ""
                name = "%s-%s%s.ttf" % (stem_name, style, suffix)
                if style == "Regular":
                    name = "%s-%s.ttf" % (stem_name, suffix or "Regular")
                path = os.path.join(args.out, name)
                n = assemble(style, weight, italic, latin, latin_cmap,
                             use_cjk, cjk_cmap, cjk_adv, cjk_vert, path,
                             plain=plain)
                log("  wrote %s  (%d glyphs, %.1f MB)"
                    % (name, n, os.path.getsize(path) / 1e6))
        log("  %.0f s" % (time.time() - t0))

    # v3.3 logged every glyph it could not correct and then exited 0 whatever
    # had happened, so nothing downstream could tell a clean build from one
    # that had given up on a thousand characters.  The validator already knows
    # what a sound face is; run it and let it decide.  Writing the targets it
    # needs (below) is what makes that answer independent of this module's
    # current globals -- see `write_build_targets`.
    if args.no_validate:
        log("\nvalidate: skipped (--no-validate)")
        return 0
    import validate
    log("\n=== validate ===")
    return validate.main(["--dir", args.out])


if __name__ == "__main__":
    sys.exit(main())
