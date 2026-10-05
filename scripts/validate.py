#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check a built face against the targets in DESIGN.md.

    python validate.py --dir fonts

Every row prints the measured value, the target and the miss.  The point of
this file is that it re-derives each target the way the build derives it and
then measures the *finished file*, so a step that silently did nothing shows up
here rather than in the user's editor.
"""
import argparse
import glob
import json
import math
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))

from fontTools.misc.transform import Transform
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont

import shapes
import build_inori_v3 as build
from build_inori_v3 import (SF, SF_WIDTH, STYLES_INDEX, STEM_CORRECTION,
                            HIRAGINO_HIRA_STEM, HIRAGINO_KATA_STEM,
                            HIRAGINO_BAR_OVER_STEM, HIRAGINO_FRAME_W,
                            HIRAGINO_FRAME_H, HIRAGINO_FRAME_C,
                            HIRAGINO_HIRA_W, HIRAGINO_HIRA_H, HIRAGINO_HIRA_RISE,
                            HIRAGINO_KATA_W, HIRAGINO_KATA_H, HIRAGINO_KATA_RISE,
                            HIRAGINO_HIRA_BAR, HIRAGINO_KATA_BAR,
                            HIRAGINO_DENSE_OVER_SIMPLE,
                            SIMPLE_SAMPLE, DENSE_SAMPLE,
                            HIRA_BAR_SAMPLE, KATA_BAR_SAMPLE,
                            _at, jp_stem_target, plan_latin,
                            KANJI_SAMPLE, FRAME_SAMPLE,
                            HIRA_SAMPLE_FULL, KATA_SAMPLE_FULL,
                            LATIN_ADV, CJK_ADV, SF_CAP, SF_ASCENDER,
                            WIDTH_CLAMP)

SIZES = (11, 12, 13, 14, 16)
_PLAN = {}
# An absolute tolerance holds a 150-unit Black stem to ten times the relative
# accuracy of a 60-unit Light one, which is not what "close enough" means here.
TOL_STEM = 2.0
TOL_STEM_REL = 0.015
TOL_RATIO = 0.06
TOL_FRAME = 20.0


def stem_tol(target):
    return max(TOL_STEM, abs(target) * TOL_STEM_REL)


def rec(f, gs, ch):
    n = f.getBestCmap().get(ord(ch))
    if not n:
        return None
    p = DecomposingRecordingPen(gs)
    gs[n].draw(p)
    return p.value


def med_stem(f, gs, chars, cuts):
    v = []
    for ch in chars:
        r = rec(f, gs, ch)
        if r:
            s = shapes.stem_of(r, cuts=cuts)
            if s:
                v.append(s)
    return statistics.median(v) if v else None


def frame(f, gs, chars):
    w, h, c = [], [], []
    for ch in chars:
        r = rec(f, gs, ch)
        b = shapes.bbox(r) if r else None
        if not b:
            continue
        w.append(b[2] - b[0])
        h.append(b[3] - b[1])
        c.append((b[1] + b[3]) / 2)
    if not w:
        return None
    return statistics.median(w), statistics.median(h), statistics.median(c)


def measured_slant(f, gs):
    """Slope of the 'l' stem, read off the outline rather than the post table."""
    r = rec(f, gs, "l")
    polys = shapes._flatten(r)
    ys = [y for p in polys for _, y in p]
    lo, hi = min(ys), max(ys)

    def centre(frac):
        y = lo + (hi - lo) * frac
        sp = shapes.spans_h(polys, y)
        return (sp[0][0] + sp[0][1]) / 2, y

    (x1, y1), (x2, y2) = centre(0.25), centre(0.55)
    return -math.degrees(math.atan2(x2 - x1, y2 - y1))


def line(label, got, want, tol, dp=1):
    ok = got is not None and abs(got - want) <= tol
    f = "%%.%df" % dp
    print("    %-26s %9s  target %9s  %-5s (miss %s)"
          % (label, f % got if got is not None else "--", f % want,
             "OK" if ok else "MISS",
             f % (got - want) if got is not None else "--"))
    return ok


def note(label, text, ok):
    print("    %-26s %9s  %s" % (label, "OK" if ok else "MISS", text))
    return ok


def digit_alignment(path):
    from PIL import Image, ImageDraw, ImageFont
    bad = []
    for px in SIZES:
        face = ImageFont.truetype(path, px)
        seen = {}
        for ch in "0123456789":
            img = Image.new("L", (px * 4, px * 4), 0)
            ImageDraw.Draw(img).text((px, px * 3), ch, font=face, fill=255, anchor="ls")
            box = img.getbbox()
            seen[ch] = (box[1], box[3]) if box else None
        if len(set(seen.values())) != 1:
            bad.append((px, seen))
    return bad


CH62 = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
KANJI_BAR_SAMPLE = "日国書語東目田口回国安京花時明線黒番"


def bar_ratio(f, gs, chars):
    """Median of each glyph's own horizontal-over-vertical."""
    v = []
    for ch in chars:
        r = rec(f, gs, ch)
        if not r:
            continue
        st = shapes.stem_of(r, cuts=shapes.CJK_CUTS)
        ba = shapes.cjk_bar_of(r)
        if st and ba:
            v.append(ba / st)
    return statistics.median(v) if v else None


#: Set from --allow-missing-source.  A check that cannot run is not a check
#: that passed: v3.2 shipped 485 broken kanji with every row reading OK, and
#: a validator that answers "OK" when it could not open the source repeats
#: that failure by construction.  Missing sources fail the run unless the
#: operator says otherwise, out loud, on the command line.
ALLOW_MISSING_SOURCE = False

#: Set from --fast.  The per-tile shape reading over all 14,224 kanji costs a
#: few minutes a face; the kana pass (176 glyphs) is always on because that is
#: where v3.3's blind spot was.
DEEP_CJK = True

#: Band for the gross ink reading, relative to the face median.  Wide on
#: purpose: this reading has a long honest tail (dakuten, brackets and small
#: marks sit at 0.87-1.13 with nothing wrong with them), and the local-excess
#: reading below is the one that judges.  This one is here for a glyph that
#: lost half of itself.
INK_GROSS = 0.25

_SOURCE = {}


def _source_table(key, cps):
    """Contour count and ink area of every source glyph in `cps`.

    The source is Noto Sans CJK JP at the three axis locations this face used.

    Returns None when the source cannot be read.
    """
    ck = (key, id(cps))
    if ck in _SOURCE:
        return _SOURCE[ck]
    try:
        src = TTFont(build.NOTO_CJK, lazy=False)
    except Exception as exc:                       # noqa: BLE001 - reported
        print("    !! source %s unreadable: %s" % (build.NOTO_CJK, exc))
        _SOURCE[ck] = None
        return None
    scm = src.getBestCmap()
    ideal = SF[key][0] * STEM_CORRECTION
    latin_stem = plan_latin(key, ideal)
    target = jp_stem_target(latin_stem / STEM_CORRECTION)
    want_frame = (_at(HIRAGINO_FRAME_W, target),
                  _at(HIRAGINO_FRAME_H, target))
    kw, hw, tw = build.plan_cjk_wghts(src, target, want_frame)
    glyphsets = {
        "kanji": src.getGlyphSet(location={"wght": kw}),
        "hira": src.getGlyphSet(location={"wght": hw}),
        "kata": src.getGlyphSet(location={"wght": tw}),
    }
    table, undrawable = {}, []
    for cp in cps:
        n = scm.get(cp)
        if not n:
            continue
        try:
            if cp in build.HIRAGANA:
                sgs = glyphsets["hira"]
            elif cp in build.KATAKANA:
                sgs = glyphsets["kata"]
            else:
                sgs = glyphsets["kanji"]
            pen = DecomposingRecordingPen(sgs)
            sgs[n].draw(pen)
        except Exception:                          # noqa: BLE001 - reported
            undrawable.append(cp)
            continue
        if pen.value:
            settled = shapes.remove_overlap(pen.value)
            table[cp] = (shapes._contours(settled),
                         abs(shapes.area(settled)), settled)
    if undrawable:
        # v3.3 swallowed these with a bare `continue`, which quietly shrank
        # the set being checked without changing the "OK" it printed.
        print("    !! %d source glyph(s) would not draw and are unchecked: %s"
              % (len(undrawable),
                 " ".join(chr(c) for c in undrawable[:12])))
    src.close()
    _SOURCE[ck] = table
    return table


KANA_CPS = tuple(list(range(0x3041, 0x3097)) + list(range(0x30A1, 0x30FB)))


def _missing_source(label):
    return note(label, "ソースが読めないので検査できない",
                ok=ALLOW_MISSING_SOURCE)


#: A glyph thinner than this in either direction is a rule, not a character.
#: Measured: the hairline rules (｜ ＿ ￣ ︱ ﹍) all sit at 34-37 units, while
#: the thinnest real strokes -- 一 70, ー 81, 丨 67 -- are twice that.
RULE_THICKNESS = 50.0


def _is_rule(rec):
    """True for a glyph that is one thin stroke and nothing else.

    The tile reading has no meaning on these.  A rule fills its own bounding
    box, so every tile it touches is either solid or empty, and a one-unit
    change in its thickness moves a whole tile from one to the other: ｜ ＿
    ￣ ︱ ﹍ all reported 0.38 against a sound population at 0.02.  There is
    no interior to compare, which is also why the build exempts the box
    drawing range from the horizontal scaling in the first place.
    """
    b = shapes.bbox(rec)
    return bool(b) and min(b[2] - b[0], b[3] - b[1]) < RULE_THICKNESS


def _fit_bbox(rec, target):
    """Put `rec` in `target`'s bounding box, so shape can be read on its own.

    The finished glyph is the source scaled by the optical factor and, for
    kana, translated by the class lift.  Comparing ink in absolute coordinates
    therefore reads a correct resize and a correct lift as damage, which is
    the reason v3.3 gave for excluding kana from the shape guard entirely.
    Normalising both sides to the same box removes size and position from the
    comparison and leaves what is actually being asked: is this still the same
    character.
    """
    b = shapes.bbox(rec)
    if not b or not target:
        return None
    # One scale for both axes, not one each.  The build only ever applies a
    # uniform resize and a translation to a CJK glyph, so that is the whole
    # family of differences this is allowed to absorb.  Fitting x and y
    # separately would also absorb a change in the glyph's proportions, and a
    # change in proportions is how a lost stroke shows itself: Regular's 屯
    # comes out 10 % narrower than the source against its own height because
    # the hook at its foot is gone.
    s = ((target[2] - target[0]) / max(b[2] - b[0], 1e-6) +
         (target[3] - target[1]) / max(b[3] - b[1], 1e-6)) / 2.0
    cx, cy = (b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0
    tx, ty = (target[0] + target[2]) / 2.0, (target[1] + target[3]) / 2.0
    return shapes.transform(rec, Transform(
        s, 0, 0, s, tx - cx * s, ty - cy * s))


def source_compare(f, gs, base_style, cps, label, shape=True, italic=False):
    """Check the finished glyphs against the source on three readings.

    Three, because none of them sees what the other two see -- the same三
    reasons the build's own guard gives, applied to the written file.

    `contours`  a stroke severed or a counter flooded shut: 攷 with the join
                between its halves cut, 懕 with a counter closed.  This is the
                v3.3 check and it stays.

    `ink`       gross loss or gain of area against the source, banded around
                the face's own median because the whole face is reshaped by
                one offset -- it is the outliers that are damage, not the
                shift.  The band is wide (`INK_GROSS`) because this reading
                has a long honest tail; it is here for 枠 losing half itself,
                not for fine judgement.

    `excess`    the largest share of any one tile the output fills and the
                source leaves blank, after both are normalised into the same
                box.  This is the reading that matters and the one v3.3 did
                not apply to kana: Medium's `ぉ` and `ゥ` came out melted and
                flooded with **the same contour count as the source at every
                fraction of the correction**, so no count rule could ever have
                seen them.  Their excess is 1.00 and 0.94 against a kana
                population whose ninth decile is 0.13.

    The excess ceiling is taken from this face and this class, not fixed:
    where the correction is an erosion the honest population sits at nothing
    (Regular kana: median 0.016), and where it is a dilation every stroke
    grows and the population moves with it (Bold kana: 0.172, with sound
    glyphs to 0.33).  A constant either misses the first or condemns the
    second.  Same formula and same constants as the build uses.
    """
    from build_inori_v3 import EXCESS_SPREADS, EXCESS_ABSOLUTE, HAND_ALL
    # A hand-redrawn character is *meant* to differ from the source, so the two
    # readings that ask "does this still match Noto" have nothing to say about
    # it.  The contour count still does -- a redraw that severed a stroke or
    # closed a counter is damage whoever drew it -- so only the shape readings
    # are dropped, and only for the handful of characters named in the build.
    # A hand-drawn character is meant to differ from the source, contour
    # count included -- `き` and `さ` join a stroke the source leaves apart,
    # `ふ` carries its first stroke into the body, `や` sits its third on
    # the bowl.  So none of the three readings has anything to say about
    # them.  What still watches these glyphs is the build: it refuses a
    # derivation that does not come out, and says so in the report.
    redrawn = {ord(ch) for ch in HAND_ALL}
    table = _source_table(base_style, cps)
    if table is None:
        return _missing_source(label)
    cmap = f.getBestCmap()
    counts, ratios, excess = [], {}, {}
    for cp, (want, src_area, src_rec) in table.items():
        if cp not in cmap:
            continue
        pen = DecomposingRecordingPen(gs)
        gs[cmap[cp]].draw(pen)
        if not pen.value:
            continue
        if cp in redrawn:
            continue
        got = shapes._contours(pen.value)
        if got != want:
            counts.append("%s %d->%d" % (chr(cp), want, got))
        if src_area > 1.0:
            ratios[cp] = abs(shapes.area(pen.value)) / src_area
        if shape and src_rec and not _is_rule(pen.value):
            # The source stands upright, so the drawing has to as well before
            # the two are laid over each other.  Shearing widens the ink box by
            # tan(10) times the glyph's height, and fitting an upright source
            # into that box stretches it sideways until every stroke misses --
            # 1,644 kanji and 44 kana read as flooded on the first italic
            # build, which was the check being wrong, not the font.  A shear
            # preserves area and cannot change topology, so only this reading
            # needs standing up; the other two are taken as shipped.
            drawn = (shapes.shear(pen.value, 0.0, pivot_y=SF_CAP / 2,
                                  src_angle_deg=-10.0) if italic
                     else pen.value)
            fitted = _fit_bbox(src_rec, shapes.bbox(drawn))
            if fitted:
                _, ex = shapes.ink_compare(drawn, fitted)
                if ex is not None:
                    excess[cp] = ex
    if not ratios:
        return _missing_source(label)

    med = statistics.median(ratios.values())
    gross = ["%s %.2f" % (chr(cp), r / med) for cp, r in sorted(ratios.items())
             if not (1.0 - INK_GROSS) <= r / med <= (1.0 + INK_GROSS)]

    flooded = []
    ceiling = None
    if excess:
        vals = sorted(excess.values())
        mid = vals[len(vals) // 2]
        p90 = vals[min(len(vals) - 1, int(0.90 * (len(vals) - 1)))]
        ceiling = min(mid + EXCESS_SPREADS * max(p90 - mid, 0.004),
                      EXCESS_ABSOLUTE)
        flooded = ["%s %.2f" % (chr(cp), e)
                   for cp, e in sorted(excess.items()) if e > ceiling]

    parts = []
    if counts:
        parts.append("輪郭数 %d 字: %s" % (len(counts), " ".join(counts[:12])))
    if gross:
        parts.append("インク %d 字: %s" % (len(gross), " ".join(gross[:12])))
    if flooded:
        parts.append("局所余剰 %d 字 (上限 %.2f): %s"
                     % (len(flooded), ceiling, " ".join(flooded[:12])))
    if parts:
        return note(label, " / ".join(parts), ok=False)
    return note(label, "OK (%d 字, ink 中央値 %.3f%s)"
                % (len(ratios), med,
                   "" if ceiling is None else ", 余剰上限 %.2f" % ceiling),
                ok=True)


def kana_topology(f, gs, base_style, italic=False):
    return source_compare(f, gs, base_style, KANA_CPS, "kana 位相/インク/余剰",
                          italic=italic)


def cjk_topology(f, gs, base_style, italic=False):
    from build_inori_v3 import is_cjk_cp
    key = base_style
    if key not in _CJK_CPS:
        try:
            src = TTFont(build.NOTO_CJK, lazy=True)
        except Exception:                          # noqa: BLE001 - reported
            _CJK_CPS[key] = None
        else:
            _CJK_CPS[key] = tuple(sorted(
                cp for cp in src.getBestCmap() if is_cjk_cp(cp)))
            src.close()
    cps = _CJK_CPS[key]
    if cps is None:
        return _missing_source("CJK 位相/インク/余剰")
    return source_compare(f, gs, base_style, cps, "CJK 位相/インク/余剰",
                          shape=DEEP_CJK, italic=italic)


_CJK_CPS = {}


def check(path):
    name = os.path.basename(path)
    plain = "MonoPlain-" in name
    style = name.split("-", 1)[1].replace(".ttf", "")
    italic = style.endswith("Italic")
    base = style.replace("Italic", "") or "Regular"
    if base not in SF:
        base = "Regular"
    print("\n%s  [%s%s%s]"
          % (name, base, " italic" if italic else "", " plain" if plain else ""))

    f = TTFont(path, lazy=False)
    gs = f.getGlyphSet()
    hmtx = f["hmtx"]
    cmap = f.getBestCmap()
    ok = True

    # Targets are re-derived exactly as the build derives them, including the
    # Geist axis limit at Black -- checking against the unreachable ideal would
    # only ever report the limit back at us.
    sf_stem, sf_bar = SF[base]
    ideal = sf_stem * STEM_CORRECTION
    stem_t = _PLAN.setdefault(base, plan_latin(base, ideal))
    reach = stem_t / ideal
    bar_t = sf_bar * STEM_CORRECTION * reach
    jp_t = jp_stem_target(stem_t / STEM_CORRECTION)
    if reach < 0.999:
        print("    (Geist axis tops out at %.1f %% of the ideal stem %.1f;"
              " targets below are the reachable ones)" % (reach * 100, ideal))

    # Widths are only comparable on a standing drawing: shearing by 10 degrees
    # adds tan(10) times the height to every ink box, which on `l` is a third
    # of its width.  The build reshapes upright and slants once at the end, so
    # the check stands the outline back up before measuring.
    def upright(r):
        if not italic or not r:
            return r
        return shapes.shear(r, 0.0, pivot_y=SF_CAP / 2, src_angle_deg=-10.0)

    # The probe is `H`, and `H` is a capital: since v4.4 the build draws the
    # capitals `build.CAP_OPTICAL` heavier than the rest of the alphabet, so
    # what this glyph should measure is the design target times that.  The
    # uncorrected target still governs everything else and is checked on the
    # lowercase `n` below.
    cap = 1.0 + build.CAP_OPTICAL
    h = rec(f, gs, "H")
    ok &= line("Latin H stem", shapes.stem_of(h), stem_t * cap,
               stem_tol(stem_t * cap))
    ok &= line("Latin H bar", shapes.bar_of(h), bar_t * cap,
               stem_tol(bar_t * cap))
    n_low = rec(f, gs, "n")
    ok &= line("Latin n stem", shapes.stem_of(upright(n_low)), stem_t,
               stem_tol(stem_t))

    # SF Mono's width rhythm.  Perfection is not the target: `W`, `X`, `Y`, `I`
    # and `j` are further from Geist than the ten-percent clamp allows, so they
    # are expected to sit short, and the gate is the mean over all 62.
    hb = shapes.bbox(h)
    h_ink_box = shapes.bbox(upright(h))
    h_ink = h_ink_box[2] - h_ink_box[0]
    col = STYLES_INDEX[base]
    errs = {}
    for ch in CH62:
        r = rec(f, gs, ch)
        b = shapes.bbox(upright(r)) if r else None
        if b:
            errs[ch] = ((b[2] - b[0]) / h_ink) / SF_WIDTH[ch][col] - 1.0
    if errs:
        mean = sum(abs(v) for v in errs.values()) / len(errs) * 100
        over = sorted(c for c, v in errs.items() if abs(v) > WIDTH_CLAMP + 0.005)
        ok &= line("width rhythm, mean err %", mean, 0.0, 2.5, dp=2)
        # Glyphs whose SF width is further away than the clamp allows stop at
        # the clamp by design (DESIGN.md 7.2), so this line reports rather
        # than judges; the mean above is the gate.
        note("width held at the clamp", "%d glyph(s) %s" % (len(over), over),
             ok=True)

    kanji = med_stem(f, gs, KANJI_SAMPLE, shapes.CJK_CUTS)
    ok &= line("CJK kanji stem", kanji, jp_t, stem_tol(jp_t))
    if kanji:
        # The same orthogonal-stroke sample the build solves on: measuring the
        # kana stem over all 46 lets the diagonals (`シ` `ス` `ツ`) set the
        # median, and their horizontal span is not a stem width.
        hira = med_stem(f, gs, HIRA_BAR_SAMPLE, shapes.CJK_CUTS)
        kata = med_stem(f, gs, KATA_BAR_SAMPLE, shapes.CJK_CUTS)
        ok &= line("hiragana/kanji stem", hira / kanji,
                   _at(HIRAGINO_HIRA_STEM, jp_t), TOL_RATIO, dp=3)
        ok &= line("katakana/kanji stem", kata / kanji,
                   _at(HIRAGINO_KATA_STEM, jp_t), TOL_RATIO, dp=3)
        # bar/stem is read per glyph and then taken as a median.  Gen Jyuu L's
        # native horizontal balance is deliberately retained; four percentage
        # points allows that source character while still catching the old
        # katakana scaling bug (which missed by about nine points).
        ok &= line("CJK bar/stem", bar_ratio(f, gs, KANJI_BAR_SAMPLE),
                   _at(HIRAGINO_BAR_OVER_STEM, jp_t), 0.04, dp=3)
        ok &= line("hiragana bar/stem", bar_ratio(f, gs, HIRA_BAR_SAMPLE),
                   _at(HIRAGINO_HIRA_BAR, jp_t), 0.03, dp=3)
        ok &= line("katakana bar/stem", bar_ratio(f, gs, KATA_BAR_SAMPLE),
                   _at(HIRAGINO_KATA_BAR, jp_t), 0.03, dp=3)
        # Hiragino holds a dense character at 0.84 of a simple one from W1 to
        # W9.  A correction applied as a flat number of units cannot preserve
        # that, which is why the build now measures every glyph.
        simple = med_stem(f, gs, SIMPLE_SAMPLE, shapes.CJK_CUTS)
        dense = med_stem(f, gs, DENSE_SAMPLE, shapes.CJK_CUTS)
        if simple >= 55:
            # Noto Regular's native 0.879 is 0.035 from Hiragino's 0.844.
            # Keep the source skeleton instead of reintroducing a per-glyph
            # boolean weight remap for a four-point population tolerance.
            #
            # The italics need 0.005 more, and it is quantisation, not design.
            # A shear preserves horizontal distances at a given y, so it cannot
            # change a stem read on horizontal cuts -- but it does move every
            # point off the integer grid, and rounding back on puts +/-1 unit
            # into each reading.  Measured over the three weights the drift
            # runs both ways: Regular 0.879 -> 0.885, Medium 0.850 -> 0.844,
            # Bold 0.849 -> 0.844, with the contour count unchanged on all 23
            # sample characters.  Regular upright already sits at 0.035 of the
            # 0.040, so the noise alone decides it.
            ok &= line("dense/simple kanji stem", dense / simple,
                       _at(HIRAGINO_DENSE_OVER_SIMPLE, jp_t),
                       0.045 if italic else 0.04, dp=3)
        else:
            # Below about 55 units every stem in the source rounds to the same
            # integer and the spread cannot be read -- Hiragino's own W0 reports
            # exactly 1.000 for the same reason.  The build leaves Light alone
            # rather than act on a number it cannot measure.
            note("dense/simple kanji stem",
                 "%.3f -- 縦画 %.0f 単位では整数丸めで分解できない（補正なし）"
                 % (dense / simple, simple), ok=True)

    # 字面 and the kana balance -- the part of the design v3.0 got wrong by
    # reading the size off a sample of narrow characters.
    fr = frame(f, gs, FRAME_SAMPLE)
    if fr:
        # An italic is sheared, which widens every ink box by tan(10) times its
        # height; the frame is checked upright only.
        if not italic:
            ok &= line("CJK frame width", fr[0],
                       _at(HIRAGINO_FRAME_W, jp_t) * build.CJK_SCALE,
                       TOL_FRAME)
        ok &= line("CJK frame height", fr[1],
                   _at(HIRAGINO_FRAME_H, jp_t) * build.CJK_SCALE, TOL_FRAME)
        ok &= line("CJK frame centre", fr[2], _at(HIRAGINO_FRAME_C, jp_t), 8.0)
        for tag, sample, wm, hm, rm in (
                ("hiragana", HIRA_SAMPLE_FULL, HIRAGINO_HIRA_W, HIRAGINO_HIRA_H,
                 HIRAGINO_HIRA_RISE),
                ("katakana", KATA_SAMPLE_FULL, HIRAGINO_KATA_W, HIRAGINO_KATA_H,
                 HIRAGINO_KATA_RISE)):
            kf = frame(f, gs, sample)
            if not kf:
                continue
            if not italic:
                ok &= line("%s width/frame" % tag, kf[0] / fr[0], _at(wm, jp_t),
                           0.035, dp=3)
            ok &= line("%s height/frame" % tag, kf[1] / fr[1], _at(hm, jp_t),
                       0.03, dp=3)
            ok &= line("%s above centre" % tag, kf[2] - fr[2],
                       _at(rm, jp_t) * build.CJK_SCALE, 8.0)

    # Topology.  `オ` shipped in v3.2 with its diagonal fused to its stem and a
    # solid wedge where the opening should be, and every check above was green:
    # a merged stroke changes no stem, no bar and no bounding box worth
    # noticing.  A kana has as many contours as the source drew it with, once
    # the boolean solver has settled both sides, and that is cheap to check.
    ok &= kana_topology(f, gs, base, italic)
    ok &= cjk_topology(f, gs, base, italic)

    lb = shapes.bbox(rec(f, gs, "l"))
    if lb and hb:
        ok &= line("ascender/cap", lb[3] / hb[3], SF_ASCENDER / SF_CAP, 0.02, dp=3)

    # A severed contour does not always raise, and it does not always show up in
    # a stem measurement: Black Italic's `2` once came out 186 units short with
    # five contours and every other check still green.  All ten digits are drawn
    # to the same two heights apart from the overshoot on the round ones, so a
    # spread wider than that means a glyph came apart.
    tops, bots, ncon = [], [], []
    for ch in "0123456789":
        r = rec(f, gs, ch)
        bb = shapes.bbox(r)
        tops.append(bb[3])
        bots.append(bb[1])
        ncon.append(len(shapes._flatten(r)))
    ok &= line("digit top spread", max(tops) - min(tops), 0.0, 30.0)
    ok &= line("digit bottom spread", max(bots) - min(bots), 0.0, 30.0)
    expected_tail = [1, 1, 1, 1, 1, 2, 1, 3, 2]
    ok &= note("digit contour counts", str(ncon),
               ncon[1:] == expected_tail and ncon[0] in (2, 3))

    # The two zeros, and the feature that swaps them.
    zname = cmap[ord("0")]
    zc = len(shapes._flatten(rec(f, gs, "0")))
    alt = "zero.alt" in f.getGlyphOrder()
    want_zc = 2 if plain else 3
    ok &= note("default zero contours", "%d (want %d)" % (zc, want_zc), zc == want_zc)
    if alt:
        pen = DecomposingRecordingPen(gs)
        gs["zero.alt"].draw(pen)
        ac = len(shapes._flatten(pen.value))
        ok &= note("zero.alt contours", "%d" % ac, ac == (3 if plain else 2))
    else:
        ok &= note("zero.alt present", "missing", False)

    feats = sorted({r.FeatureTag for r in
                    f["GSUB"].table.FeatureList.FeatureRecord}) if "GSUB" in f else []
    want_feats = {"ss01", "cv01", "vert", "vrt2"} | ({"zero"} if plain else set())
    ok &= note("GSUB features", " ".join(feats), want_feats <= set(feats))

    # Every codepoint gets exactly one right answer, not a choice of two.  The
    # old form of this check accepted "600 or 1200" for anything outside the
    # CJK block, which is precisely how 1846 Greek, Cyrillic, IPA and symbol
    # glyphs shipped at double width without failing a single run.  It then
    # asked `is_cjk_cp`, which is a source rule and stops at U+FFE6, and so
    # agreed with the build that 303 Extension B ideographs belonged in a
    # half-width cell.  Both now ask the same width rule.
    bad_adv = []
    for cp, n in cmap.items():
        want = 0 if build.zero_advance(cp) else (CJK_ADV if build.is_fullwidth_cp(cp) else LATIN_ADV)
        got = hmtx[n][0]
        if got != want:
            bad_adv.append((hex(cp), got, want))
    ok &= note("advance widths",
               "OK" if not bad_adv else "%d wrong, e.g. %s"
               % (len(bad_adv), bad_adv[:5]), not bad_adv)

    # The two rows below are about where the drawing sits in its cell, and an
    # italic has no answer to that question.  Geist Italic puts its own `H` 19
    # units right of centre and its `.` 43 left, because a slanted letter is
    # balanced by eye at the height it is read, not by its bounding box; it
    # also leans past the cell edge on purpose.  Standing the outline back up
    # does not help -- it only trades the source's pivot for ours.  Since v4.5
    # the build answers the question its own way, by moving each slanted
    # letter until its ink balances where the upright's ink balanced, which is
    # a placement no box measurement here can confirm.  Every weight ships an
    # upright face built by the same code, so measuring those covers the
    # family.
    if italic:
        ok &= note("cell placement", "skipped (italic)", True)
    else:
        # Ink that runs past its own cell is ink the next character has to
        # share.
        spill = []
        for cp, n in cmap.items():
            g = f["glyf"][n]
            if not getattr(g, "numberOfContours", 0):
                continue
            # Box drawing, blocks and shades are tiles, not letters: Geist
            # bleeds the rules five units each side so neighbours meet, and
            # draws the shades as a dot field that deliberately overhangs.
            # They are checked for tiling below instead.
            if 0x2500 <= cp <= 0x259F:
                continue
            adv = hmtx[n][0]
            if adv == 0:  # Combining marks intentionally attach outside a zero-width origin.
                continue
            if g.xMin < 0 or g.xMax > adv:
                spill.append((hex(cp), g.xMin, g.xMax, adv))
        ok &= note("ink inside the cell",
                   "OK" if not spill else "%d spill, e.g. %s"
                   % (len(spill), spill[:5]), not spill)

        # The Latin and the CJK have to share one optical centre.  Reading it
        # off glyphs that are symmetrical by construction catches a cell-wide
        # shift that no per-glyph target would notice.
        def mid(ch):
            nm = cmap.get(ord(ch))
            g = f["glyf"][nm] if nm else None
            if not nm or not getattr(g, "numberOfContours", 0):
                return None
            return (g.xMin + g.xMax) / 2.0 - hmtx[nm][0] / 2.0

        offs = [m for m in (mid(c) for c in "HInoxTW0.:|-") if m is not None]
        joff = [m for m in (mid(c) for c in "国日回田口目") if m is not None]
        lat_off = statistics.median(offs) if offs else 0.0
        cjk_off = statistics.median(joff) if joff else 0.0
        ok &= note("Latin centred in cell", "%+.1f (want 0 +/- 3)" % lat_off,
                   abs(lat_off) <= 3.0)
        ok &= note("CJK centred in cell", "%+.1f (want 0 +/- 3)" % cjk_off,
                   abs(cjk_off) <= 3.0)

    # Box drawing has to tile.  A rule that stops short of the cell edge leaves
    # a gap in every run of it, which no stem or frame measurement can see.
    tiles = []
    for cp in (0x2500, 0x2501, 0x2588):
        nm = cmap.get(cp)
        g = f["glyf"][nm] if nm else None
        if not nm or not getattr(g, "numberOfContours", 0):
            continue
        if g.xMin > 0 or g.xMax < hmtx[nm][0]:
            tiles.append((hex(cp), g.xMin, g.xMax, hmtx[nm][0]))
    ok &= note("box drawing tiles",
               "OK" if not tiles else "gaps: %s" % (tiles,), not tiles)

    # The pairing the whole family rests on, measured on the finished file and
    # compared with the constant it is supposed to reproduce -- not with a
    # number re-derived from the same build code, which cannot fail.
    lat_stem = med_stem(f, gs, "H", shapes.STEM_CUTS)
    cjk_stem = med_stem(f, gs, KANJI_SAMPLE, shapes.CJK_CUTS)
    if lat_stem and cjk_stem:
        ratio = cjk_stem / lat_stem
        # The model is anchored on SF Mono Regular paired with Hiragino W3 and
        # narrows as the weight rises, so the target is read off the measured
        # Latin rather than fixed -- but it comes from the *model*, not from
        # the build's own STEM_CORRECTION, which is the constant this row
        # exists to catch.
        want = jp_stem_target(lat_stem) / lat_stem
        ok &= note("CJK/Latin stem ratio",
                   "%.3f (%.1f / %.1f, want %.3f +/- 0.035)"
                   % (ratio, cjk_stem, lat_stem, want),
                   abs(ratio - want) <= 0.035)

    # What Windows reads.  A face that declares no code page is one no legacy
    # charset claims, and the shell lays it out as if it covered nothing; a
    # usWin box tighter than the ink clips the glyphs that reach past it.
    o = f["OS/2"]
    ink_top = max(g.yMax for g in f["glyf"].glyphs.values()
                  if getattr(g, "numberOfContours", 0))
    ink_bot = min(g.yMin for g in f["glyf"].glyphs.values()
                  if getattr(g, "numberOfContours", 0))
    ok &= note("OS/2 version", str(o.version), o.version >= 4)
    ok &= note("OS/2 code pages", hex(o.ulCodePageRange1),
               bool(o.ulCodePageRange1 & (1 << 17)) and bool(o.ulCodePageRange1 & 1))
    ok &= note("OS/2 avg char width", str(o.xAvgCharWidth),
               o.xAvgCharWidth == LATIN_ADV)
    ok &= note("usWin box covers ink",
               "%d/%d vs ink %d/%d" % (o.usWinAscent, o.usWinDescent,
                                       ink_top, -ink_bot),
               o.usWinAscent >= ink_top and o.usWinDescent >= -ink_bot)
    ok &= note("strikeout / subscript",
               "%d / %d" % (o.yStrikeoutSize, o.ySubscriptYSize),
               o.yStrikeoutSize > 0 and o.ySubscriptYSize > 0)
    ok &= note(".notdef drawn",
               "%d contours" % f["glyf"][".notdef"].numberOfContours,
               f["glyf"][".notdef"].numberOfContours > 0)

    ang = float(f["post"].italicAngle)
    ok &= line("italic angle (post)", ang, -10.0 if italic else 0.0, 0.3, dp=2)
    ok &= line("italic angle (drawn)", measured_slant(f, gs), -10.0 if italic else 0.0,
               0.6, dp=2)

    f.close()

    bad = digit_alignment(path)
    ok &= note("digit alignment",
               "OK" if not bad else "off at %s px" % [b[0] for b in bad], not bad)
    return ok


def main(argv=None):
    global LATIN_ADV, CJK_ADV, ALLOW_MISSING_SOURCE, DEEP_CJK
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="fonts")
    ap.add_argument("--allow-missing-source", action="store_true",
                    help="源フォントが読めないとき、その検査を落として続行する"
                         "（既定は失敗。v3.2 の事故と同じ形なので明示させる）")
    ap.add_argument("--fast", action="store_true",
                    help="漢字の局所余剰検査を省く（仮名は必ず検査する）")
    ap.add_argument("--no-targets", action="store_true",
                    help="build-targets.json を読まずに引数と既定値で検証する")
    ap.add_argument("--cell", type=int, default=LATIN_ADV,
                    help="expected Latin advance (CJK is twice this value)")
    ap.add_argument("--widen", type=float, default=build.LATIN_WIDEN,
                    help="Latin widening used by the build")
    ap.add_argument("--cjk-scale", type=float, default=build.CJK_SCALE,
                    help="optical CJK frame scale used by the build")
    args = ap.parse_args(argv)
    ALLOW_MISSING_SOURCE = args.allow_missing_source
    DEEP_CJK = not args.fast

    # The targets below are re-derived from `build_inori_v3`'s formulas, which
    # is deliberate -- the formulas are the specification.  The *parameters*
    # are not: they belong to one build, and until v3.3 they came from this
    # file's own defaults, so a build run with `--widen 1.2` and a check run
    # without it agreed on every row while measuring against the wrong target.
    # The build now writes what it used next to the fonts; read that, and say
    # so loudly when it is not there.
    cell, widen, cjk_scale = args.cell, args.widen, args.cjk_scale
    tpath = os.path.join(args.dir, "build-targets.json")
    if args.no_targets:
        print("targets: --no-targets, using %s" % os.path.basename(__file__))
    elif os.path.exists(tpath):
        with open(tpath, encoding="utf-8") as fh:
            t = json.load(fh)
        cell, widen, cjk_scale = t["cell"], t["widen"], t["cjk_scale"]
        print("targets: %s (%s, cell %s, widen %s, cjk-scale %s)"
              % (tpath, t.get("version"), cell, widen, cjk_scale))
    else:
        print("targets: %s が無い。このディレクトリを作ったビルドが何を目標に"
              "していたか分からないので検証しない。--no-targets で強行できる。"
              % tpath)
        return 1

    LATIN_ADV = cell
    CJK_ADV = cell * 2
    build.LATIN_WIDEN = widen
    build.LATIN_XS = widen
    build.CJK_SCALE = cjk_scale
    _PLAN.clear()
    files = sorted(glob.glob(os.path.join(args.dir, "*.ttf")))
    if not files:
        print("no fonts in %s" % args.dir)
        return 1
    results = [(os.path.basename(p), check(p)) for p in files]
    print("\n%d/%d faces pass" % (sum(1 for _, o in results if o), len(results)))
    for n, o in results:
        if not o:
            print("  FAIL %s" % n)
    return 0 if all(o for _, o in results) else 1


if __name__ == "__main__":
    sys.exit(main())
