"""Hand-drawn character -> font outline.

The screenshot is a brush drawing: antialiased, a little shaky, and at
whatever size the phone canvas was.  Four steps get it into the font.

  ink      threshold, dropping the app's coloured chrome and any speck
  smooth   blur and re-threshold, then trace the *float* field at 0.5 --
           sub-pixel, so the pixel staircase never reaches the outline
  curve    emit a quadratic spline: turns sharper than CORNER stay on-curve
           so stroke ends keep their cut, everything else rounds
  fit      one scale onto the box the character already occupies, then
           dilate or erode to this weight's own stroke width

Nothing here reshapes what was drawn.  Every attempt to do that -- turning
`と`'s rising stroke to Hiragino's slope, squaring `や`'s head off -- got
the number right and the glyph wrong, because the corrections land on the
junctions, which is the part the drawing exists to settle.
"""
import math

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter
from skimage import measure

from . import shapes

CORNER = 22.0      # degrees of turn that counts as a corner, not a curve


def ink(path, top=None, bot=None, floor=400):
    """Binary ink from a drawing.

    A screenshot carries the paint app's toolbars and a coloured banner, so
    rows outside the canvas are cut and anything coloured is dropped.  A
    plain exported drawing has neither, so when no crop is given, take the
    whole image.
    """
    a = np.array(Image.open(path).convert("RGB")).astype(int)
    if top is not None or bot is not None:
        a = a[top or 0:bot if bot is not None else len(a)]
    m = ((a.mean(2) < 128) & ((a.max(2) - a.min(2)) < 60))
    lab = measure.label(m)
    keep = np.zeros_like(m)
    for r in measure.regionprops(lab):
        if r.area >= floor:
            keep[lab == r.label] = True
    return keep


def outlines(mask, blur=1.0, tol=1.1):
    # Blur only enough to take the pixel staircase off the edge.  The first
    # version used four pixels and a 55-degree corner test, and between them
    # they rounded the brush's own square cuts off `き` and `ふ`: a corner is
    # smoothed by the blur before the tracer sees it, and what survives is
    # then under the threshold and gets drawn as a curve.
    field = gaussian_filter(np.pad(mask, 8).astype(float), blur)
    rings = []
    for c in measure.find_contours(field, 0.5):
        s = measure.approximate_polygon(c, tolerance=tol)
        if len(s) < 8:
            continue
        pts = [(float(x - 8), float(-(y - 8))) for y, x in s[:-1]]
        if _area(pts) < 0:
            pts.reverse()
        rings.append(pts)
    return rings


def _area(p):
    return sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1]
               for i in range(len(p))) / 2.0


def _turn(a, b, c):
    import math
    v = math.atan2(b[1] - a[1], b[0] - a[0])
    w = math.atan2(c[1] - b[1], c[0] - b[0])
    d = math.degrees(w - v)
    return abs((d + 180.0) % 360.0 - 180.0)


def spline(pts):
    """Quadratic spline through `pts`, keeping the sharp turns sharp."""
    n = len(pts)
    sharp = [_turn(pts[i - 1], pts[i], pts[(i + 1) % n]) > CORNER
             for i in range(n)]
    rec, start = [], next((i for i, s in enumerate(sharp) if s), 0)
    order = [(start + k) % n for k in range(n)]
    rec.append(("moveTo", (pts[order[0]],)))
    run = []
    for i in order[1:] + [order[0]]:
        if sharp[i]:
            rec.append(("qCurveTo", tuple(run) + (pts[i],)) if run
                       else ("lineTo", (pts[i],)))
            run = []
        else:
            run.append(pts[i])
    if run:
        rec.append(("qCurveTo", tuple(run) + (pts[order[0]],)))
    rec.append(("closePath", ()))
    return rec


def stroke_width(mask):
    """The width of the brush, read at the centreline.

    Not area over centreline length, which is what this did first.  A
    hand-drawn edge wobbles, so `skeletonize` returns a longer centreline
    with more spurs than the same character drawn by machine, and dividing
    by it reports a stroke wider than it is.  It said Bold `き` and `ふ`
    matched the originals; measured properly they were 19 and 29 units
    thin, which is exactly what they looked like on the page.

    So take the distance to the nearest edge *at* the centreline and double
    it -- that is the local width wherever it is measured, and the median
    over the character is immune to how long the centreline came out.
    """
    from scipy.ndimage import distance_transform_edt
    from skimage.morphology import skeletonize
    sk = skeletonize(mask)
    if not sk.any():
        return None
    return float(np.median(distance_transform_edt(mask)[sk])) * 2.0


def raster(rec, size=900):
    """Fill a recording-pen path into a boolean array, for measuring."""
    from PIL import ImageDraw
    polys = shapes._flatten(rec)
    x0, y0, x1, y1 = shapes.bbox(rec)
    s = (size - 20) / max(x1 - x0, y1 - y0)
    img = Image.new("L", (size, size), 0)
    acc = np.zeros((size, size), dtype=bool)
    for p in polys:
        m = Image.new("L", (size, size), 0)
        ImageDraw.Draw(m).polygon(
            [(10 + (x - x0) * s, size - 10 - (y - y0) * s) for x, y in p],
            fill=255)
        acc ^= np.array(m) > 127
    return acc, s


def fit(rings, target_rec, weight_scale=1.0):
    """Scale the drawing onto the box the character already occupies."""
    xs = [p[0] for r in rings for p in r]
    ys = [p[1] for r in rings for p in r]
    sx0, sy0, sx1, sy1 = min(xs), min(ys), max(xs), max(ys)
    tx0, ty0, tx1, ty1 = shapes.bbox(target_rec)
    s = (ty1 - ty0) / (sy1 - sy0) * weight_scale
    cx, cy = (sx0 + sx1) / 2.0, (sy0 + sy1) / 2.0
    ox, oy = (tx0 + tx1) / 2.0, (ty0 + ty1) / 2.0
    return [[((x - cx) * s + ox, (y - cy) * s + oy) for x, y in r]
            for r in rings], s


def _split_mark(rec):
    """Body and mark of a glyph, the way the build already tells them apart.

    A dakuten or handakuten is small against the glyph and sits in its
    top-right corner.  Matching contour areas between the plain and voiced
    glyphs was tried instead and is not safe -- areas drift between weights,
    and one mis-pair slides the body into the mark, which came out as a
    Medium `ぷ` reaching 487 units below the baseline.
    """
    x0, y0, x1, y1 = shapes.bbox(rec)
    w, h = x1 - x0, y1 - y0
    mark, body = [], []
    for c in shapes.contours(rec):
        cb = shapes.bbox(c)
        small = (cb[2] - cb[0]) < 0.30 * w and (cb[3] - cb[1]) < 0.30 * h
        corner = ((cb[0] + cb[2]) / 2 - x0) / w > 0.55 and \
                 ((cb[1] + cb[3]) / 2 - y0) / h > 0.55
        (mark if small and corner else body).extend(c)
    # Normalise the winding.  Contours pulled straight out of the source
    # keep the direction the font drew them in, while everything else here
    # has been through skia and carries skia's.  Union the two and the marks
    # cancel against the body instead of adding to it: Medium `ざ` came out
    # at 91,753 units against a body of 194,085, and read as a hole.
    return (shapes.remove_overlap(body, "body") if body else body,
            shapes.remove_overlap(mark, "mark") if mark else mark)


def _difference(a, b):
    import pathops
    out = pathops.Path()
    pathops.difference([shapes.to_path(a)], [shapes.to_path(b)], out.getPen())
    return shapes.from_path(out)


def _to_width(rec, want, name, rounds=6):
    """Dilate or erode until the stroke is `want` wide, and no further.

    `dilate_checked` reports success on a step that quietly ruins the glyph:
    small kana `ゃ` has a bowl whose counter is nearly shut, and the fourth
    step there took the contour count from one to two and the area *down*
    while asking for more ink.  Nothing downstream noticed -- the signed
    area and the raster agreed with each other, because both were measuring
    the same wrecked outline -- and Medium shipped a hollow bowl.  So keep
    the last shape that still has the topology it started with, and stop at
    the first step that does not.
    """
    keep = shapes._contours(rec)
    for _ in range(rounds):
        r, sc = raster(rec, 1200)
        d = (want - stroke_width(r) / sc) / 2.0
        if abs(d) < 0.4:
            break
        cand, ok = shapes.dilate_checked(rec, d, name)
        if not ok:
            break
        settled = shapes.remove_overlap(cand, name)
        if shapes._contours(settled) != keep:
            break
        if (d > 0) != (abs(shapes.area(settled)) > abs(shapes.area(rec))):
            break
        rec = settled
    return rec


def restyle(new_base, target, name="restyle", marked=True, plain=None):
    """Carry a redrawn character into the glyphs built out of it.

    `ど` is `と` plus a dakuten, `ゃ` is `や` at four fifths, `ぎ` `ぶ` `ぷ`
    are the same story.  The build makes each of them from the source, so
    redrawing `と` and leaving them alone ships a font whose `と` and `ど`
    are different characters -- which is what the first bake did.

    The mark is kept exactly as it was drawn; only the body is replaced,
    fitted to the room that body already occupies (which is not the plain
    character's box -- small kana are narrowed more than they are shortened)
    and thinned or thickened back to the width it had.
    """
    from fontTools.misc.transform import Transform
    # `marked` says whether this glyph has a dakuten at all.  Asking the
    # shape instead does not work: the small kana `ゃ` keeps `や`'s third
    # stroke, which is small and sits in the top right, so the rule that
    # finds a dakuten finds that instead -- the body came out as the bowl
    # alone, the whole of `や` was squeezed into it, and Medium shipped a
    # hollow loop.
    body, mark = _split_mark(target) if marked else (target, [])
    if not body:
        return None
    if marked and shapes._contours(mark) == 1:
        # One stroke of the dakuten is already touching the bar at this
        # weight, so collecting separate contours finds the other one and
        # only that one -- Medium and Bold `ざ` have three contours where
        # Regular has four.  Replacing the body would then ship half a
        # dakuten.  The two strokes are the same shape, so put a copy of
        # the one that is loose where the fused one sits: the offset is the
        # one Regular reports, in this glyph's own width and height.
        x0, y0, x1, y1 = shapes.bbox(target)
        cb = shapes.bbox(mark)
        if ((cb[0] + cb[2]) / 2 - x0) / (x1 - x0) > 0.85:
            mark = mark + shapes.transform(
                mark, Transform(1, 0, 0, 1,
                                -0.136 * (x1 - x0), -0.043 * (y1 - y0)))
    return _place(new_base, body, mark, name)


def _place(new_base, body, mark, name):
    from fontTools.misc.transform import Transform
    bx0, by0, bx1, by1 = shapes.bbox(body)
    nx0, ny0, nx1, ny1 = shapes.bbox(new_base)
    sx = (bx1 - bx0) / (nx1 - nx0)
    sy = (by1 - by0) / (ny1 - ny0)
    ras, sc = raster(body, 1200)
    want = stroke_width(ras) / sc
    # Even fitted to that box the two can touch: the redrawn `き` carries its
    # top bar higher on the right than the source does, and at Medium and
    # Bold the tip ran into the lower dakuten stroke and merged with it.  The
    # mark has to stay a mark, so back the body off to the left until it
    # clears -- a few units, and only where it is needed.
    fallback = None
    for back in (0.0, 10.0, 20.0, 30.0, 45.0, 60.0):
        t = (Transform()
             .translate((bx0 + bx1) / 2.0 - back, (by0 + by1) / 2.0)
             .scale(sx, sy)
             .translate(-(nx0 + nx1) / 2.0, -(ny0 + ny1) / 2.0))
        fitted = shapes.remove_overlap(shapes.transform(new_base, t), name)
        fitted = _to_width(fitted, want, name)
        out = fitted + mark
        if not mark:
            return dedupe(out)
        if (shapes._contours(shapes.remove_overlap(out, name)) ==
                shapes._contours(fitted) + shapes._contours(mark)):
            return dedupe(out)
        if fallback is None:
            fallback = (out, fitted)
    # No offset keeps the mark clear of the body.  On `ざ` at Medium and Bold
    # that is the source's own drawing -- the lower dakuten stroke touches
    # the bar there too -- so take the first placement as long as the mark's
    # ink is still all there, and only give up if it is being swallowed.
    if fallback is not None:
        out, fitted = fallback
        joined = shapes.remove_overlap(out, name)
        if abs(shapes.area(joined)) >= (abs(shapes.area(fitted))
                                        + 0.80 * abs(shapes.area(mark))):
            return dedupe(out)
    return None


def dedupe(rec, eps=1.5):
    """Drop points that land on top of the one before them.

    A traced outline carries a point every few source pixels.  Scaled into
    the glyph and rounded to the integer grid, a good number of them come
    out on the same coordinate -- 94 of Medium `ゃ`'s 356.  skia is happy
    with that and so is the signed area, which is why every measurement said
    the glyph was sound; FreeType is not, and rendered the bowl as a hairline
    outline with the fill inside out.
    """
    import math
    out, last = [], None
    for op, args in rec:
        if op == "closePath":
            out.append((op, args))
            last = None
            continue
        if op == "moveTo":
            out.append((op, args))
            last = args[0]
            continue
        end = args[-1]
        if end is None or last is None:
            out.append((op, args))
            last = end or last
            continue
        if math.hypot(end[0] - last[0], end[1] - last[1]) <= eps:
            continue                      # goes nowhere; the curve with it
        keep, prev = [], last
        for p in args[:-1]:
            if math.hypot(p[0] - prev[0], p[1] - prev[1]) > eps:
                keep.append(p)
                prev = p
        out.append((op, tuple(keep) + (end,)) if keep or op != "qCurveTo"
                   else ("lineTo", (end,)))
        last = end
    return out


def _norm(mask, n=900, width=None):
    """Ink cropped and scaled to height `n`, keeping its proportions.

    Squaring it here is what made the grafted `さ` 830 units wide against a
    696-unit box: the two drawings went onto a square grid, so the bowl came
    back stretched, and the glyph was then wide enough to run into `ざ`'s
    dakuten.
    """
    ys, xs = np.nonzero(mask)
    crop = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = crop.shape
    scaled = np.array(Image.fromarray((crop * 255).astype(np.uint8))
                      .resize((max(1, round(n * w / h)), n),
                              Image.LANCZOS)) > 127
    if width is None:
        return scaled
    out = np.zeros((n, width), bool)
    out[:, :min(width, scaled.shape[1])] = scaled[:, :width]
    return out


def graft(host, donor, cut, n=900):
    """Put the donor's bottom onto the host, joined at height `cut`.

    `さ` and `き` are the same character below the bars, and Hiragino draws
    them that way -- the same bowl, sitting 0.05 lower in `き` to make room
    for the second bar.  Drawn by hand they came out as two different bowls
    (IoU 0.639 over the lower half), so take one bowl and use it for both.

    The seam goes where both glyphs have nothing crossing it but the
    diagonal.  Sliding the donor sideways to meet it was the first attempt
    and it narrowed the bowl: the diagonal lined up, but the whole bowl went
    with it and the gap between the bar's left end and the bowl closed from
    0.041 of the width to 0.118.  So map the donor's width instead of moving
    it -- one linear map in x that puts its diagonal on the host's diagonal
    *and* its left edge on the host's left edge.  The bowl then keeps the
    host's width and the donor's shape.
    """
    wide = max(_norm(host, n).shape[1], _norm(donor, n).shape[1])
    h, d = _norm(host, n, wide), _norm(donor, n, wide)
    row = int(n * (1.0 - cut))

    def marks(m):
        at = np.nonzero(m[row])[0]
        below = np.nonzero(m[row:].any(0))[0]
        if not len(at) or not len(below):
            return None
        return (at.min() + at.max()) / 2.0, float(below.min())

    a, b = marks(h), marks(d)
    if a is None or b is None or abs(b[0] - b[1]) < 1.0:
        return None
    scale = (a[0] - a[1]) / (b[0] - b[1])
    shift = a[0] - scale * b[0]
    tail = np.zeros((n, wide), bool)
    xs = np.arange(wide)
    src = np.round((xs - shift) / scale).astype(int)
    ok = (src >= 0) & (src < wide)
    tail[:, ok] = d[:, src[ok]]
    out = h.copy()
    out[row:] = False
    out[row:] |= tail[row:]
    return out


# `lift_rise` was here: it turned `と`'s rising stroke about its tip to put
# the slope on Hiragino's 0.289.  The number came out right and the glyph
# came out wrong -- dropping the junction end pulls the first stroke's foot
# down with it, and fading that shift out with height stretched the foot
# into a hanging spike with a step where it met the rise.  A hand-drawn
# junction is the one thing a warp should not be touching; that is what the
# drawing was for.  If the slope wants changing it gets redrawn.


def fit_to(rings, target, name):
    """Scale a traced drawing onto the glyph it replaces, and match weight.

    Scale and thicken have to be solved together, not in sequence:
    thickening grows the ink box by the same amount it adds to the stroke,
    so a drawing scaled to the right height comes out too tall once it is
    dilated -- Bold `き` was 22 units over the box it was fitted to.  So
    fit, thicken, measure the box, correct the scale, and go round again.
    """
    ras, sc = raster(target, 1200)
    want_w = stroke_width(ras) / sc
    tb = shapes.bbox(target)
    want_h = tb[3] - tb[1]
    k, best = 1.0, None
    for _ in range(4):
        placed, _s = fit(rings, target, k)
        rec = shapes.remove_overlap(
            [op for r in placed for op in spline(r)], name)
        rec = _to_width(rec, want_w, name)
        bb = shapes.bbox(rec)
        best = rec
        if abs((bb[3] - bb[1]) - want_h) < 3.0:
            break
        k *= want_h / (bb[3] - bb[1])
    return dedupe(best) if best else None
