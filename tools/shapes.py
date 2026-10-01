#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Outline surgery primitives for the Inori Mono v3 build.

Everything works on fontTools RecordingPen value lists (a list of
``(operator, args)`` tuples) so callers never have to think about pens.

The one non-obvious tool here is anisotropic dilation.  ``dilate`` grows or
shrinks a contour by the same amount in every direction, which is all skia's
stroker offers.  But a condensed Latin needs its horizontal bars thinned
*without* touching its vertical stems: after squeezing x by 0.83 the stems come
down with the width while the bars stay exactly as thick as they were, and the
glyph reads as reverse-contrast.

The trick is to do the isotropic operation in a deliberately distorted space.
Scale x by a large K, erode by e, scale x back by 1/K: the erosion takes e/2 off
the top and bottom (unchanged by the x scale) and e/(2K) off each side, which
after the inverse scale is e/(2K^2) -- nothing.  So horizontal bars lose e and
vertical stems lose e/K^2.  With K = 20 that cross-talk is a quarter of a
percent, well under the rounding at the end of the build.  Swapping the axes
gives the same control over vertical stems.
"""
import math
import statistics

import pathops
from PIL import Image, ImageChops, ImageDraw
from fontTools.misc.transform import Transform
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen

# Cross-talk is 1/K^2, so 20 buys 0.25 % -- far below the final rounding.
ANISO_K = 20.0


# --------------------------------------------------------------------------
# recording-pen plumbing


def transform(rec, t):
    """Apply an affine Transform to a recording."""
    out = RecordingPen()
    pen = TransformPen(out, t)
    for op, args in rec:
        getattr(pen, op)(*args)
    return out.value


def scale(rec, sx, sy=None):
    return transform(rec, Transform(sx, 0, 0, sy if sy is not None else sx, 0, 0))


def translate(rec, dx, dy=0):
    return transform(rec, Transform(1, 0, 0, 1, dx, dy))


def shear(rec, angle_deg, pivot_y=0.0, src_angle_deg=0.0):
    """Slant to `angle_deg` (negative = leaning right, the CSS/post convention).

    `src_angle_deg` is the recording's existing italic angle.  Real italic
    masters are already slanted, and a source drawn at -10 deg that has since
    been condensed by 0.83 now leans at atan(0.83*tan10) = 8.4 deg, so shearing
    it by a further 10 would overshoot.  Subtracting the source's own slope
    makes the result land on `angle_deg` no matter what came before; with
    src_angle 0 this is the ordinary oblique shear.
    """
    dst = math.tan(math.radians(-angle_deg))
    src = math.tan(math.radians(-src_angle_deg))
    return transform(rec, Transform(1, 0, dst - src, 1, -(dst - src) * pivot_y, 0))


# --------------------------------------------------------------------------
# boolean operations


def to_path(rec):
    p = pathops.Path()
    pen = p.getPen(glyphSet=None)
    for op, args in rec:
        getattr(pen, op)(*args)
    p.simplify(fix_winding=True, keep_starting_points=False)
    return p


def from_path(p):
    p.convertConicsToQuads()
    r = RecordingPen()
    p.draw(r)
    return r.value


def remove_overlap(rec, tag=None):
    if not rec:
        return rec
    try:
        return prune(from_path(to_path(rec)))
    except pathops.PathOpsError:
        failures.append((tag, "overlap"))
        return rec


#: glyphs skia refused to dilate, by (caller-supplied) tag -- see `failures`
failures = []


def dilate_checked(rec, amount, tag=None):
    """`dilate`, returning `(outline, ok)` instead of signalling with identity.

    Every guard in the build used to read "did this work?" as
    `out is not rec` -- the caller's safety resting on the callee's habit of
    returning the very same object on the failure path.  Nothing enforced that
    habit and nothing tested it, so any refactor that returned a copy on
    failure would have turned every guard in the pipeline off in silence.  Say
    it in the return type instead.  `dilate` stays as it was for the callers
    that only want the outline.
    """
    return _dilate(rec, amount, tag)


def dilate(rec, amount, tag=None):
    """Grow (amount > 0) or shrink (amount < 0) by |amount|/2 on every side.

    A stem bounded by two contours therefore changes by exactly `amount`.

    Skia's path solver can fail outright on a degenerate contour -- a hairline
    at Light that the erosion would consume entirely, a self-touching curve the
    simplifier leaves ambiguous.  A single such glyph must not take down a
    7000-glyph build, so a failure leaves that one outline as it was and is
    recorded in `failures` for the caller to report.
    """
    return _dilate(rec, amount, tag)[0]


def _dilate(rec, amount, tag=None):
    if not rec or abs(amount) < 1e-6:
        return rec, False
    try:
        orig = to_path(rec)
        stroke = pathops.Path()
        stroke.addPath(orig)
        stroke.stroke(abs(amount), pathops.LineCap.BUTT_CAP,
                      pathops.LineJoin.MITER_JOIN, 4.0)
        out = pathops.Path()
        pen = out.getPen(glyphSet=None)
        if amount > 0:
            pathops.union([orig, stroke], pen)
        else:
            pathops.difference([orig], [stroke], pen)
        result = from_path(out)
    except pathops.PathOpsError:
        failures.append((tag, round(amount, 2)))
        return rec, False
    if not result:                       # erosion consumed the glyph
        failures.append((tag, round(amount, 2)))
        return rec, False
    result = prune(result)
    # An erosion may not change the topology at all.  More contours than it
    # started with means a stroke was severed; *fewer* means one was severed the
    # other way and two counters ran into each other -- eroding `8` five percent
    # narrower breaks its waist and turns three contours into two.  A dilation
    # is not held to this: closing a counter in a dense kanji is what thickening
    # it is supposed to look like.
    if amount < 0 and _tore(rec, result):
        failures.append((tag, "torn: %d -> %d contours"
                         % (_contours(rec), _contours(result))))
        return rec, False
    return result, True


def _contours(rec):
    return sum(1 for op, _ in rec if op in ("closePath", "endPath"))


def _tore(rec_before, rec_after):
    """True when an erosion damaged the outline rather than just thinning it.

    Counting the contours of the input directly would be wrong: a decomposed
    composite carries its accent as a contour of its own that overlaps the
    letter, and the boolean solver merges the two on the way through, so `Ç`
    goes from two contours to one without anything having gone wrong.  The
    comparison has to be against the input *as the solver sees it*, which costs
    one more union -- so it is only paid when the cheap count disagrees.
    """
    after = _contours(rec_after)
    if after == _contours(rec_before):
        return False
    try:
        settled = _contours(from_path(to_path(rec_before)))
    except pathops.PathOpsError:
        return False
    # One contour more is what thinning a dense character is *supposed* to do:
    # two strokes drawn touching come apart, or a pinched counter opens into
    # two.  Two or more is the shredding that put Black Italic's `2` at five
    # contours.  Fewer is always wrong -- eroding cannot merge anything except
    # by severing a stroke, which is how `8` loses its waist.
    return after > settled + 1 or after < settled


#: Square units.  The smallest counter anyone draws at 1000 upem -- the eye of
#: a dense kanji -- is a few hundred; a sliver left by the solver is under
#: twenty.  A hundred sits an order of magnitude clear of both.
SLIVER_AREA = 100.0


def prune(rec, min_area=SLIVER_AREA):
    """Drop contours too small to be anything but a solver artefact.

    Dilating in the stretched space the anisotropic tools work in means running
    the stroker over a shape twenty times taller than it is meant to be, and on
    a smooth curve skia occasionally leaves a hair-thin self-intersection
    behind.  Scaled back down these are hairs six units wide and a couple of
    square units in area -- invisible, but they multiply the contour count,
    which is exactly the signal the tear detector reads, and they turned `0`
    from three contours into eleven.
    """
    if not rec:
        return rec
    keep = []
    for c in contours(rec):
        if abs(area(c)) >= min_area:
            keep.extend(c)
    return keep if keep else rec


def ink_mask(rec, box=48, steps=12):
    """Rasterise an outline to a square bitmap, normalised to its own ink.

    Ink area is blind to the damage that matters most: 追 came back with its
    walking radical destroyed and its 白 flooded into two solid blocks, and the
    total ink barely moved, because what a counter lost a blob gained.  Shape
    has to be compared as shape.  The two sides being compared sit in different
    cells -- a 1200-unit output glyph against a 1000-unit source -- so each is
    cropped to its own ink and scaled to the same box before they are laid over
    one another.

    Contours are filled with the even-odd rule by XOR-ing each one in turn,
    which is what makes a counter a hole without having to know which way it
    was wound.
    """
    parts = contours(rec)
    if not parts:
        return None
    polys = [[p for p in _flatten(c, steps=steps) if len(p) > 2] for c in parts]
    pts = [q for pp in polys for p in pp for q in p]
    if not pts:
        return None
    xs = [q[0] for q in pts]
    ys = [q[1] for q in pts]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    if w <= 0.0 or h <= 0.0:
        return None
    acc = Image.new("1", (box, box), 0)
    for pp in polys:
        for poly in pp:
            layer = Image.new("1", (box, box), 0)
            ImageDraw.Draw(layer).polygon(
                [((x - min(xs)) / w * (box - 1),
                  (box - 1) - (y - min(ys)) / h * (box - 1)) for x, y in poly],
                fill=1)
            acc = ImageChops.logical_xor(acc, layer)
    return acc


def _mask_in(rec, frame, box, steps):
    """Rasterise `rec` into a caller-supplied frame rather than its own ink.

    `ink_mask` normalises each outline to its own bounding box, which is what
    a shape comparison wants and a *position* comparison must not have: the
    corrected glyph is thinner than the source, so its box is a few units
    smaller, and normalising each to its own box slides one against the other
    by a fraction of a pixel everywhere.  That shift alone put 和 at 0.33 on
    the excess statistic with nothing wrong with it.  These two outlines are
    already in the same design coordinates, so share the frame and the shift
    is gone.
    """
    x0, y0, x1, y1 = frame
    w, h = x1 - x0, y1 - y0
    if w <= 0.0 or h <= 0.0:
        return None
    acc = Image.new("1", (box, box), 0)
    for contour in contours(rec):
        for poly in _flatten(contour, steps=steps):
            if len(poly) <= 2:
                continue
            layer = Image.new("1", (box, box), 0)
            ImageDraw.Draw(layer).polygon(
                [((x - x0) / w * (box - 1),
                  (box - 1) - (y - y0) / h * (box - 1)) for x, y in poly],
                fill=1)
            acc = ImageChops.logical_xor(acc, layer)
    return acc


def ink_compare(rec_a, rec_b, box=64, steps=2, tile=8):
    """How `a` differs from `b`, globally and locally, in a shared frame.

    Returns ``(iou, excess)``.  ``iou`` is the whole-glyph overlap.  ``excess``
    is the largest share of any one tile that `a` fills and `b` leaves blank,
    and it exists because the whole-glyph numbers are blind to the failure
    that matters most here: an erosion that floods the *gap between* two
    strokes closes no counter, so the contour count is right, and fills a few
    percent of the glyph, so the ink total is right, and it survives an
    overlap floor because most of the character is still there.  談 薬 鶏 遮 坐
    -- five 常用漢字 -- all shipped with a solid black block in them and every
    whole-glyph test green.  Cut the glyph into tiles and the block fills its
    own tile, while a glyph that merely came out thinner adds ink nowhere.

    The mirror statistic -- ink the source has and `a` does not -- is
    deliberately not returned.  Thinning removes ink along every edge, so a
    tile over a hairline stroke empties for entirely honest reasons, and a
    stroke lost outright changes the contour count anyway.
    """
    ba, bb = bbox(rec_a), bbox(rec_b)
    if not ba or not bb:
        return None, None
    frame = (min(ba[0], bb[0]), min(ba[1], bb[1]),
             max(ba[2], bb[2]), max(ba[3], bb[3]))
    a = _mask_in(rec_a, frame, box, steps)
    b = _mask_in(rec_b, frame, box, steps)
    if a is None or b is None:
        return None, None
    pa, pb = list(a.getdata()), list(b.getdata())
    union = sum(1 for u, v in zip(pa, pb) if u or v)
    if not union:
        return None, None
    iou = sum(1 for u, v in zip(pa, pb) if u and v) / float(union)
    # Count the ink in each tile on both sides and take the difference, rather
    # than counting the pixels where `a` is set and `b` is not.  The two are
    # the same thing for a flood and very different for a stroke that moved:
    # thinning slides every edge inwards by a fraction of a pixel, so a
    # per-pixel test lights up along the whole outline for entirely honest
    # reasons (和 and 爬 reached 0.33 and 0.22 with nothing wrong with them),
    # while the tile's ink total barely moves because the pixels the stroke
    # gains on one side it loses on the other.  A flood has no such symmetry:
    # it fills its tile and nothing gives the ink back.
    worst = 0
    span = tile * tile
    for ty in range(0, box, tile):
        for tx in range(0, box, tile):
            diff = 0
            for dy in range(tile):
                row = (ty + dy) * box + tx
                for dx in range(tile):
                    if pa[row + dx]:
                        diff += 1
                    if pb[row + dx]:
                        diff -= 1
            if diff > worst:
                worst = diff
    return iou, worst / float(span)


def ink_iou(rec_a, rec_b, box=48, steps=12):
    """Overlap of two outlines once both are normalised -- 1.0 is identical."""
    a, b = ink_mask(rec_a, box, steps), ink_mask(rec_b, box, steps)
    if a is None or b is None:
        return None
    pa, pb = list(a.getdata()), list(b.getdata())
    union = sum(1 for u, v in zip(pa, pb) if u or v)
    if not union:
        return None
    return sum(1 for u, v in zip(pa, pb) if u and v) / float(union)


def _intact(rec_before, rec_after, axis, amount, tag):
    """Reject a reshape that tore the outline apart.

    Skia does not always raise when an erosion severs a stroke: at Black the
    italic `2` came back with five contours and a top edge 186 units low, and
    nothing had thrown.

    The test cannot simply be "the bounding box moved by amount/2", because for
    a pointed glyph it legitimately moves much further -- eroding `A`
    vertically makes its apex retreat down the diagonal, several times the
    erosion depth.  What a severed contour does that a correct one does not is
    multiply the contour count and take a large *fraction* of the glyph with
    it, so those are what is checked.

    `axis` is 1 when the operation is meant to move the height, 0 the width.
    """
    before, after = bbox(rec_before), bbox(rec_after)
    if before is None or after is None:
        return False
    # A successful boolean can still return the stroke *around* a filled
    # contour instead of the filled contour itself.  Its bounding box looks
    # perfect and a positive dilation is allowed to add contours, so neither
    # check below catches it; `2` became a hairline outline this way.  A modest
    # stem/bar adjustment cannot legitimately discard half the signed fill.
    before_area = abs(area(rec_before))
    after_area = abs(area(rec_after))
    if before_area > 1.0 and after_area < before_area * 0.5:
        failures.append((tag, "lost %.0f%% of filled area"
                         % ((1.0 - after_area / before_area) * 100)))
        return False
    if before_area > 1.0 and after_area > before_area * 1.5:
        failures.append((tag, "gained %.0f%% of filled area"
                         % ((after_area / before_area - 1.0) * 100)))
        return False
    # Only an erosion can tear.  A dilation that splits one counter into two
    # -- which is what closing a gap in a dense kanji looks like -- raises the
    # contour count by design, and rejecting those left a thousand characters
    # at the wrong weight.
    if amount < 0 and _tore(rec_before, rec_after):
        failures.append((tag, "torn: %d -> %d contours"
                         % (_contours(rec_before), _contours(rec_after))))
        return False
    dims_b = (before[2] - before[0], before[3] - before[1])
    dims_a = (after[2] - after[0], after[3] - after[1])
    for i in (0, 1):
        expected = amount if i == axis else 0.0
        slack = max(4.0 * abs(amount), 0.15 * dims_b[i], 8.0)
        if abs((dims_a[i] - dims_b[i]) - expected) > slack:
            failures.append((tag, "lost %.0f of %.0f on axis %d"
                             % (dims_b[i] - dims_a[i], dims_b[i], i)))
            return False
    return True


def adjust_bars(rec, amount, k=ANISO_K, tag=None):
    """Change horizontal-bar thickness by `amount`, leaving vertical stems alone."""
    return adjust_bars_checked(rec, amount, k, tag)[0]


def adjust_bars_checked(rec, amount, k=ANISO_K, tag=None):
    """`adjust_bars`, returning `(outline, ok)`.  See `dilate_checked`."""
    if not rec or abs(amount) < 1e-6:
        return rec, False
    r2, ok = _dilate(scale(rec, k, 1.0), amount, tag)
    if not ok:
        return rec, False
    # Prune again on the way back: in the stretched space a sliver's area is
    # multiplied by k, so the check inside `dilate` cannot see it there.
    out = prune(scale(r2, 1.0 / k, 1.0))
    if not _intact(rec, out, 1, amount, tag):
        return rec, False
    return out, True


def adjust_stems(rec, amount, k=ANISO_K, tag=None):
    """Change vertical-stem thickness by `amount`, leaving horizontal bars alone."""
    return adjust_stems_checked(rec, amount, k, tag)[0]


def adjust_stems_checked(rec, amount, k=ANISO_K, tag=None):
    """`adjust_stems`, returning `(outline, ok)`.  See `dilate_checked`."""
    if not rec or abs(amount) < 1e-6:
        return rec, False
    r2, ok = _dilate(scale(rec, 1.0, k), amount, tag)
    if not ok:
        return rec, False
    out = prune(scale(r2, 1.0, 1.0 / k))
    if not _intact(rec, out, 0, amount, tag):
        return rec, False
    return out, True


def dilate_graded(rec, amount, tag=None, steps=(1.0, 0.66, 0.33)):
    """`dilate`, settling for less rather than for nothing.

    The per-glyph kanji correction asks the densest characters for the largest
    erosions, which is exactly where the solver gives up.  Refusing outright
    left a hundred characters a full correction away from their neighbours;
    two thirds of it is not the number the design asked for, but it is three
    times closer than none.
    """
    if not rec or abs(amount) < 1e-6:
        return rec, 0.0
    mark = len(failures)
    for f in steps:
        if abs(amount * f) < 0.2:
            break
        out, ok = dilate_checked(rec, amount * f, tag)
        if ok:
            del failures[mark:]
            return out, f
    del failures[mark:]
    failures.append((tag, "stem %+.1f: no step survived" % amount))
    return rec, 0.0


def adjust_bars_graded(rec, amount, tag=None, steps=(1.0, 0.66, 0.33)):
    """Thin the horizontal bars, settling for less rather than for nothing.

    A dense kanji cannot always give up the full correction: the erosion meets
    itself between two bars that are three units apart and severs the glyph,
    and `adjust_bars` correctly refuses.  Refusing outright left six hundred
    characters at Regular carrying bars a full 6 % heavier than their
    neighbours.  Two thirds of the correction is not the answer the design
    asked for, but it is four times closer than none, and a glyph that survives
    at 2 % off is worth more than one that is right in principle and torn.
    """
    if not rec or abs(amount) < 1e-6:
        return rec, 0.0
    mark = len(failures)
    for f in steps:
        out, ok = adjust_bars_checked(rec, amount * f, tag=tag)
        if ok:
            del failures[mark:]          # the earlier attempts are not news
            return out, f
    del failures[mark:]
    failures.append((tag, "bar %+.1f: no step survived" % amount))
    return rec, 0.0


def scale_about(rec, sx, sy=1.0, cx=0.0, cy=0.0):
    """Scale around an arbitrary point instead of the origin."""
    return transform(rec, Transform(sx, 0, 0, sy,
                                    cx * (1 - sx), cy * (1 - sy)))


def close_gaps(rec, d, tag=None):
    """Morphological closing: fill any gap narrower than `d`.

    Dilating and then eroding by the same amount leaves a convex boundary
    exactly where it was and fills every concavity too narrow for the
    structuring element to enter.  It is how the slash comes out of a slashed
    zero: the counter of such a zero is one ellipse cut in two, and closing the
    two halves across the cut gives back the ellipse the designer started from,
    without having to guess at its curvature.
    """
    if not rec or d <= 0:
        return rec
    grown = dilate(rec, d, tag)
    if grown is rec:
        return rec
    return dilate(grown, -d, tag)


def contours(rec):
    """Split at contour endings, including TrueType all-off-curve contours.

    Such a contour starts with qCurveTo(..., None), not moveTo. Splitting
    only at moveTo merged circles into adjacent contours and could prune or
    miscount them during the topology checks.
    """
    out, cur = [], []
    for op, args in rec:
        if op == "moveTo" and cur:
            out.append(cur)
            cur = []
        cur.append((op, args))
        if op in ("closePath", "endPath"):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def area(rec):
    """Signed area, by the shoelace formula on the flattened outline."""
    total = 0.0
    for poly in _flatten(rec):
        n = len(poly)
        for i in range(n):
            x0, y0 = poly[i]
            x1, y1 = poly[(i + 1) % n]
            total += x0 * y1 - x1 * y0
    return total / 2.0


def centroid(rec):
    """Where the ink balances, by the same shoelace on the same flattening.

    `bbox` answers where a glyph *reaches*; this answers where it *is*.  For
    an upright glyph the two nearly agree, which is why the cell centring is
    written on the box.  Slant the glyph and they part company: the box is set
    by whichever two points happen to lean furthest, and for `1` those are the
    ends of the foot serif, which the slant barely moves, while the whole stem
    above them travels right.
    """
    total = 0.0
    cx = cy = 0.0
    for poly in _flatten(rec):
        n = len(poly)
        for i in range(n):
            x0, y0 = poly[i]
            x1, y1 = poly[(i + 1) % n]
            cross = x0 * y1 - x1 * y0
            total += cross
            cx += (x0 + x1) * cross
            cy += (y0 + y1) * cross
    if abs(total) < 1e-9:
        return None
    return (cx / (3.0 * total), cy / (3.0 * total))


# --------------------------------------------------------------------------
# measurement (scanline, no rasteriser)


def _flatten(rec, steps=24):
    polys, cur, last = [], [], None

    def q(p0, p1, p2):
        for i in range(1, steps + 1):
            t = i / steps
            m = 1 - t
            yield (m * m * p0[0] + 2 * m * t * p1[0] + t * t * p2[0],
                   m * m * p0[1] + 2 * m * t * p1[1] + t * t * p2[1])

    def c(p0, p1, p2, p3):
        for i in range(1, steps + 1):
            t = i / steps
            m = 1 - t
            yield (m ** 3 * p0[0] + 3 * m * m * t * p1[0] + 3 * m * t * t * p2[0] + t ** 3 * p3[0],
                   m ** 3 * p0[1] + 3 * m * m * t * p1[1] + 3 * m * t * t * p2[1] + t ** 3 * p3[1])

    for op, args in rec:
        if op == "moveTo":
            if cur:
                polys.append(cur)
            cur = [args[0]]
            last = args[0]
        elif op == "lineTo":
            cur.append(args[0])
            last = args[0]
        elif op == "qCurveTo":
            pts = list(args)
            if pts[-1] is None:  # all-off-curve TrueType contour
                mid = ((pts[0][0] + pts[-2][0]) / 2, (pts[0][1] + pts[-2][1]) / 2)
                pts = pts[:-1] + [mid]
                last = mid
            on, off = pts[-1], pts[:-1]
            prev = last
            for i, ctl in enumerate(off):
                nxt = on if i == len(off) - 1 else ((ctl[0] + off[i + 1][0]) / 2,
                                                   (ctl[1] + off[i + 1][1]) / 2)
                cur.extend(q(prev, ctl, nxt))
                prev = nxt
            last = on
        elif op == "curveTo":
            pts = list(args)
            if len(pts) == 3:
                cur.extend(c(last, pts[0], pts[1], pts[2]))
            else:
                cur.extend(pts)
            last = pts[-1]
        elif op == "closePath":
            if cur:
                polys.append(cur)
                cur = []
    if cur:
        polys.append(cur)
    return polys


def _cross(polys, coord, axis):
    """Filled intervals along `axis` (0 = horizontal cut, 1 = vertical cut)."""
    hits = []
    for poly in polys:
        n = len(poly)
        for i in range(n):
            a, b = poly[i], poly[(i + 1) % n]
            u0, u1 = (a[1], b[1]) if axis == 0 else (a[0], b[0])
            v0, v1 = (a[0], b[0]) if axis == 0 else (a[1], b[1])
            if u0 == u1:
                continue
            if (u0 <= coord < u1) or (u1 <= coord < u0):
                t = (coord - u0) / (u1 - u0)
                hits.append((v0 + t * (v1 - v0), 1 if u1 > u0 else -1))
    hits.sort()
    out, wind, start = [], 0, None
    for v, d in hits:
        if wind == 0:
            start = v
        wind += d
        if wind == 0 and start is not None:
            out.append((start, v))
            start = None
    return out


def spans_h(polys, y):
    """Horizontal filled runs at height y -- these are vertical-stem widths."""
    return _cross(polys, y, 0)


def spans_v(polys, x):
    """Vertical filled runs at abscissa x -- these are horizontal-bar heights."""
    return _cross(polys, x, 1)


def bbox(rec):
    polys = _flatten(rec)
    if not polys:
        return None
    xs = [x for p in polys for x, _ in p]
    ys = [y for p in polys for _, y in p]
    return min(xs), min(ys), max(xs), max(ys)


STEM_CUTS = (0.15, 0.22, 0.30, 0.70, 0.78, 0.85)
CJK_CUTS = (0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.85)


def stem_and_bar(rec, cuts=CJK_CUTS, limit=300.0, steps=10):
    """Vertical-stem and horizontal-bar thickness from a single flattening.

    The per-glyph corrections need both numbers for every character in the
    font, and flattening a dense kanji is the expensive part; doing it once and
    cutting the same polygons in both directions halves that.  `steps` is lower
    than the default because a stroke width does not need a curve resolved to a
    fortieth of a unit.
    """
    polys = _flatten(rec, steps=steps)
    if not polys:
        return None, None
    xs = [x for p in polys for x, _ in p]
    ys = [y for p in polys for _, y in p]
    lo, hi = min(ys), max(ys)
    w = [b - a for r in cuts for a, b in spans_h(polys, lo + (hi - lo) * r)]
    w = [x for x in w if x < limit]
    lo, hi = min(xs), max(xs)
    v = [b - a for r in cuts for a, b in spans_v(polys, lo + (hi - lo) * r)]
    v = [x for x in v if x < limit]
    return (statistics.median(w) if w else None,
            statistics.median(v) if v else None)


def stem_of(rec, cuts=STEM_CUTS, limit=300.0):
    """Median vertical-stem width, sampled away from any crossbar."""
    polys = _flatten(rec)
    if not polys:
        return None
    ys = [y for p in polys for _, y in p]
    lo, hi = min(ys), max(ys)
    w = [b - a for r in cuts for a, b in spans_h(polys, lo + (hi - lo) * r)]
    w = [x for x in w if x < limit]
    return statistics.median(w) if w else None


def bar_of(rec, limit=300.0):
    """Thickest horizontal bar down the middle of the glyph."""
    polys = _flatten(rec)
    if not polys:
        return None
    xs = [x for p in polys for x, _ in p]
    v = [b - a for a, b in spans_v(polys, (min(xs) + max(xs)) / 2)]
    v = [x for x in v if x < limit]
    return max(v) if v else None


def cjk_bar_of(rec, limit=300.0):
    """Median horizontal-bar thickness of a CJK glyph, sampled across its width."""
    polys = _flatten(rec)
    if not polys:
        return None
    xs = [x for p in polys for x, _ in p]
    lo, hi = min(xs), max(xs)
    v = [b - a for r in CJK_CUTS for a, b in spans_v(polys, lo + (hi - lo) * r)]
    v = [x for x in v if x < limit]
    return statistics.median(v) if v else None
