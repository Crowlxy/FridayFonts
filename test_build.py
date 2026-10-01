#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Self-checks for the contracts the build's guards rest on.

    python test_build.py

No framework on purpose.  Every case here is a contract that was stated in a
comment, relied on by a guard, and never checked -- which is how v3.3 shipped
`ぉ` and `ゥ` destroyed with every row of `validate.py` reading OK.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))
import shapes                                                    # noqa: E402
import build_inori_v3 as build                                   # noqa: E402
from fontTools.misc.transform import Transform                    # noqa: E402


def box(x0, y0, x1, y1):
    return [("moveTo", ((x0, y0),)), ("lineTo", ((x1, y0),)),
            ("lineTo", ((x1, y1),)), ("lineTo", ((x0, y1),)),
            ("closePath", ())]


def test_dilate_reports_success_explicitly():
    """S9: a guard must not have to read success off object identity."""
    sq = box(0, 0, 100, 100)
    out, ok = shapes.dilate_checked(sq, 10.0, "square")
    assert ok, "a 10-unit dilation of a 100-unit square must succeed"
    assert abs(shapes.area(out)) > abs(shapes.area(sq))
    # A no-op amount is not a success, and must say so rather than returning
    # the same object and leaving the caller to notice.
    same, ok = shapes.dilate_checked(sq, 0.0, "square")
    assert not ok and same is sq
    empty, ok = shapes.dilate_checked([], 10.0, "empty")
    assert not ok
    # The thin wrapper the rest of the build still uses keeps its old shape.
    assert shapes.dilate(sq, 10.0, "square") is not sq


def test_dilate_grows_a_stem_by_the_amount_asked():
    """The whole weight model rests on this: `amount` is the stem change."""
    bar = box(0, 0, 40, 400)
    out = shapes.dilate(bar, 12.0, "bar")
    b = shapes.bbox(out)
    got = b[2] - b[0]
    assert abs(got - 52.0) < 1.0, "40 + 12 expected, got %.2f" % got


def test_settle_largest_takes_the_largest_passing_rung():
    """S5: the accepted set is not an interval, so bisection is not sound.

    `probe`'s real test is `_contours(settled) == keep`, an equality over a
    quantity that is not monotone in the offset.  Model that here: 0.75 works
    and 0.5 does not.  A bisection starting at (0, 1) probes 0.5, fails, and
    can never look above it again; the ladder finds 0.75.
    """
    tried = []

    def probe(f):
        tried.append(f)
        return "outline" if (f == 0.75 or f <= 0.25) else None

    got, took = build.settle_largest(probe)
    assert got == "outline", "an accepted fraction exists and must be found"
    assert took == 0.75, "expected the largest passing rung, got %r" % took
    assert tried[0] == 1.0, "the ladder starts at the full correction"

    def never(f):
        return None

    assert build.settle_largest(never) == (None, 0.0)


def test_area_window_tightens_with_the_correction():
    """S4: the window has to come from the offset, not be a constant."""
    tight = build.area_window(1.9, 77.7)      # Medium's global offset
    loose = build.area_window(9.44, 107.9)    # Bold's
    assert tight < loose < 0.45
    assert loose < 0.55, "must be tighter than the constant it replaced"
    assert build.area_window(0.0, 100.0) == 0.08, "floor for tiny offsets"
    assert build.area_window(1e6, 1.0) == 0.45, "and a ceiling"

    sq = box(0, 0, 100, 100)
    a = abs(shapes.area(sq))
    assert build.in_area_window(sq, a, 0.10)
    assert not build.in_area_window(box(0, 0, 100, 50), a, 0.10)


def test_kana_ink_outlier_is_what_catches_a_flooded_counter():
    """S1/S2: the count is constant across this damage; the ink is not.

    `ぉ` is three contours in the source and three in every shipped weight,
    so no count rule can see what happened to it.  The rule that does see it
    is the one the build already computes -- ink against the source, banded
    around the face median -- and this is that rule, in miniature.
    """
    from build_inori_v3 import INK_TOLERANCE
    ratios = {"a": 1.12, "b": 1.13, "c": 1.11, "d": 1.14,
              "flooded": 1.49, "melted": 1.30}
    import statistics
    med = statistics.median(ratios.values())
    lo, hi = med * (1 - INK_TOLERANCE), med * (1 + INK_TOLERANCE)
    bad = {n for n, r in ratios.items() if not lo <= r <= hi}
    assert bad == {"flooded", "melted"}, bad


def test_rules_are_excluded_from_the_shape_reading():
    """A hairline rule has no interior, so the tile reading lies about it.

    Measured in the shipped Regular: the rules (｜ ＿ ￣ ︱ ﹍) are 34-37
    units thick and all reported an excess of 0.38 against a population at
    0.02.  The thinnest real strokes -- 一 70, ー 81, 丨 67 -- are twice
    that, so a cut at 50 separates them with room on both sides.
    """
    import validate
    assert validate._is_rule(box(0, 0, 34, 1051)), "｜ is a rule"
    assert validate._is_rule(box(0, 0, 1052, 35)), "＿ is a rule"
    assert not validate._is_rule(box(0, 0, 954, 70)), "一 is a character"
    assert not validate._is_rule(box(0, 0, 67, 956)), "丨 is a character"
    assert not validate._is_rule(box(0, 0, 817, 947)), "屯 is a character"


def test_validate_note_has_no_default_verdict():
    """S6: `note(label, text)` used to print OK.  It must not be callable."""
    import inspect
    import validate
    sig = inspect.signature(validate.note)
    assert sig.parameters["ok"].default is inspect.Parameter.empty


def test_kana_rhythm_moves_kana_without_reshaping_them():
    """The rhythm pass is a translation, and a voiced kana follows its base.

    The point of the test is the second half.  が has to end up where か is,
    measured on the body and not on the box, because the dakuten sits above
    everything and would otherwise drag the answer 20 units off.
    """
    # か at centre 400, が drawn 30 units low with a mark in the top right.
    ka = box(100, 250, 500, 550)
    ga = box(100, 220, 460, 520) + box(470, 620, 540, 690)
    out = {"ka": ka, "ga": ga}
    cmap = {ord("か"): "ka", ord("が"): "ga"}
    shift = build.kana_rhythm(out, cmap)

    assert "ga" in shift, "が must be nudged onto か"
    assert abs(shift["ga"] - 30.0) < 0.01, shift["ga"]
    # か is the only unvoiced kana here, so it is its own class mean and the
    # bias subtraction has to leave it exactly where the class lift put it.
    # Without that subtraction it would move by its own table entry and take
    # the whole syllabary's optical height with it.
    assert "ka" not in shift, shift

    moved = shapes.transform(ga, Transform(1, 0, 0, 1, 0, shift["ga"]))
    assert len(shapes.contours(moved)) == len(shapes.contours(ga))
    assert abs(abs(shapes.area(moved)) - abs(shapes.area(ga))) < 0.01
    before, after = shapes.bbox(ga), shapes.bbox(moved)
    assert abs((after[2] - after[0]) - (before[2] - before[0])) < 0.01
    assert abs((after[3] - after[1]) - (before[3] - before[1])) < 0.01

    # The mark is what makes the body reading necessary: read the whole box
    # instead and the answer is wrong by more than the correction itself.
    assert abs(build._voiced_body(ga)[3] - 520) < 0.01


def test_all_off_curve_contours_survive_splitting_and_pruning():
    circle = [("qCurveTo", ((0, 100), (100, 100), (100, 0), (0, 0), None)), ("closePath", ())]
    two = circle + shapes.translate(circle, 200)
    assert shapes._contours(two) == 2
    assert len(shapes.contours(two)) == 2
    assert shapes._contours(shapes.prune(two)) == 2
    assert abs(shapes.area(two) - 2 * shapes.area(circle)) < 0.001


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    bad = 0
    for t in tests:
        try:
            t()
        except AssertionError as exc:
            bad += 1
            print("FAIL %s: %s" % (t.__name__, exc))
        else:
            print("ok   %s" % t.__name__)
    print("\n%d/%d passed" % (len(tests) - bad, len(tests)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
