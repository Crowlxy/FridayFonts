"""Repair outline defects 5.0 inherits from the 4.93 fonts.

The 4.9x Light, Medium, SemiBold and italic faces were derived by moving
outlines, and a few glyphs came out with a contour running the wrong way.
Under the non-zero fill rule such a contour cuts a hole where it should add
ink:

  * the acute of A-ring-acute and the A-circumflex/breve-acute capitals is an
    outline plus a reversed copy of itself, so it draws hollow (Regular,
    Medium) or half filled (Light, Light Italic);
  * the ogonek of Light A E I U a i u is reversed, so it is cut away where it
    crosses the stem;
  * tildes in SemiBold Italic and Light Italic carry a small reversed loop,
    a white notch in the middle or at the end of the wave.

`reversed_contours` finds them by geometry, not by name.  A reversed contour
is a real counter when it lies inside the ink of the glyph's other contours
and keeps a stroke's distance from the contour that encloses it.  A defect
either sticks out of the ink (the ogonek) or runs along the outline of the
contour around it (the doubled acute, the tilde loops).  A counter closed
by crossing strokes also runs along the outline; the three glyphs where that
is meant are listed in COUNTERS.  A contour that sticks out is turned round;
one inside the ink is removed.  Either way its area becomes ink again and
no other point moves.

Two glyphs are broken in their point structure instead and are rebuilt from
points that are still in the glyph (`splice_light_dje`) or replaced by the
Regular / Italic outline (`rebuild_from_reference`).
"""
import math

import pathops
from fontTools.pens.pointPen import PointToSegmentPen
from fontTools.ttLib.tables import ttProgram

NEAR = 8          # font units: a point this close to the enclosing outline runs along it
ALONG = 0.3       # share of a contour's points that must run along the outline
OUTSIDE = 0.05    # share of a reversed contour's area outside the other contours' ink
# counters closed by crossing strokes that run along the outline and are
# meant (checked by eye in every weight): the triangle under the bar of
# K-vertical-stroke, between arrow and stroke in the negated arrows
COUNTERS = {0x49E, 0x219A, 0x219B}


def _contours(glyph, glyf):
    coords, ends, flags = glyph.getCoordinates(glyf)
    out, start = [], 0
    for end in ends:
        out.append(list(range(start, end + 1)))
        start = end + 1
    return coords, flags, out


def _signed_area(points):
    return sum(points[k - 1][0] * points[k][1] - points[k][0] * points[k - 1][1]
               for k in range(len(points))) / 2


def _fill(coords, flags, contours):
    path = pathops.Path()
    pen = PointToSegmentPen(path.getPen())
    for contour in contours:
        pen.beginPath()
        for i in contour:
            pen.addPoint(tuple(coords[i]), 'qcurve' if flags[i] & 1 else None)
        pen.endPath()
    path.simplify(fix_winding=True)
    return path


def _area(path):
    return abs(path.area)


def _segment_distance(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy
    t = 0 if not length else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / length))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def reversed_contours(glyph, glyf, allowed=False):
    """Indices of contours that run the wrong way (see the module docstring).

    `allowed`: the glyph is in COUNTERS; only the sticking-out test is made.
    Returns (index, sticks out) pairs.
    """
    if glyph.numberOfContours < 2:
        return []
    coords, flags, contours = _contours(glyph, glyf)
    areas = [_signed_area([coords[i] for i in c]) for c in contours]
    sense = 1 if sum(areas) > 0 else -1
    outer = [k for k, a in enumerate(areas) if a * sense > 0]
    found = []
    for k, a in enumerate(areas):
        if a * sense >= 0:
            continue
        hole = _fill(coords, flags, [contours[k]])
        size = _area(hole)
        if size < 1:
            continue
        ink = _fill(coords, flags, [contours[j] for j in outer])
        outside = _area(pathops.op(hole, ink, pathops.PathOp.DIFFERENCE))
        if outside > OUTSIDE * size:
            found.append((k, True))
            continue
        pts = [coords[i] for i in contours[k]]
        if allowed:
            continue
        for j in outer:
            single = _fill(coords, flags, [contours[j]])
            if _area(pathops.op(hole, single, pathops.PathOp.DIFFERENCE)) > 0.02 * size:
                continue
            ring = [coords[i] for i in contours[j]]
            near = sum(1 for p in pts
                       if min(_segment_distance(p, ring[m - 1], ring[m]) for m in range(len(ring))) <= NEAR)
            if near >= ALONG * len(pts):
                found.append((k, False))
                break
    return found


def reverse_contour(glyph, contour):
    """Reverse one contour in place, keeping an on-curve point first."""
    first, last = contour[0], contour[-1]
    coords = [glyph.coordinates[i] for i in contour][::-1]
    flags = [glyph.flags[i] for i in contour][::-1]
    shift = next(m for m, f in enumerate(flags) if f & 1)
    coords, flags = coords[shift:] + coords[:shift], flags[shift:] + flags[:shift]
    for m, i in enumerate(range(first, last + 1)):
        glyph.coordinates[i] = coords[m]
        glyph.flags[i] = flags[m]


def meant_counters(font):
    """Glyph names of COUNTERS (mapped or not)."""
    return {font.getBestCmap().get(cp) for cp in COUNTERS} | {'uni%04X' % cp for cp in COUNTERS}


def remove_contour(glyph, contour):
    """Delete one contour (its point indices) from a simple glyph."""
    from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
    first, last = contour[0], contour[-1]
    size = last - first + 1
    glyph.coordinates = GlyphCoordinates(list(glyph.coordinates[:first]) + list(glyph.coordinates[last + 1:]))
    glyph.flags = glyph.flags[:first] + glyph.flags[last + 1:]
    glyph.endPtsOfContours = [e if e < first else e - size for e in glyph.endPtsOfContours if e != last]
    glyph.numberOfContours = len(glyph.endPtsOfContours)


def fix_reversed(font):
    """Repair every wrongly running contour.  Returns {glyph: [(contour, action)]}.

    One that sticks out of the ink (the ogonek) is turned round so its own
    area is ink.  One inside the ink (a doubled acute, a tilde loop) is
    removed: turning a tilde loop round would leave its pointed ends as
    needles on the outline.
    """
    glyf = font['glyf']
    meant = meant_counters(font)
    fixed = {}
    for name in font.getGlyphOrder():
        glyph = glyf[name]
        if glyph.numberOfContours < 2:
            continue
        found = reversed_contours(glyph, glyf, name in meant)
        if not found:
            continue
        _, _, contours = _contours(glyph, glyf)
        for k, sticks_out in found:
            if sticks_out:
                reverse_contour(glyph, contours[k])
        for k, sticks_out in sorted(found, reverse=True):
            if not sticks_out:
                remove_contour(glyph, contours[k])
        glyph.recalcBounds(glyf)
        fixed[name] = [(k, 'turned round' if out else 'removed') for k, out in found]
    return fixed


def splice_light_dje(font):
    """Light U+0402: put the inner arc of the bowl back into the outline.

    4.93 Light runs the inner side of the bowl as a separate contour that
    goes out and comes back the same way (zero area), and the outline itself
    jumps from the stem straight to the end of the hook, so the counter is
    filled.  The first half of the stray contour is exactly the missing arc:
    it starts on the stem point and ends on the hook point the outline jumps
    between.  It is spliced in and the stray contour dropped.
    """
    glyf = font['glyf']
    name = font.getBestCmap().get(0x402)
    glyph = glyf[name] if name else None
    if glyph is None or glyph.numberOfContours != 2:
        return False
    coords, flags, contours = _contours(glyph, glyf)
    main, stray = contours
    pts = [tuple(coords[i]) for i in stray]
    jump = turn = None
    for m in range(len(main)):
        a, b = tuple(coords[main[m]]), tuple(coords[main[(m + 1) % len(main)]])
        if math.dist(a, pts[0]) > 2 or math.dist(a, b) < 50:
            continue
        hits = [t for t in range(1, len(pts)) if math.dist(pts[t], b) <= 2]
        if hits:
            jump, turn = m, hits[0]
    if jump is None:
        return False
    arc = list(range(1, turn))           # strictly between the stem and hook points
    new_coords, new_flags = [], []
    for m, i in enumerate(main):
        new_coords.append(tuple(coords[i]))
        new_flags.append(flags[i])
        if m == jump:
            for a in arc:
                new_coords.append(pts[a])
                new_flags.append(flags[stray[a]])
    from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
    glyph.coordinates = GlyphCoordinates(new_coords)
    glyph.flags = bytearray(f & 1 for f in new_flags)
    glyph.endPtsOfContours = [len(new_coords) - 1]
    glyph.numberOfContours = 1
    glyph.recalcBounds(glyf)
    return True


def rebuild_from_reference(font, reference, cp):
    """Replace a glyph whose contours fell apart by the reference weight's.

    Used for U+212E (estimated sign) in Light and Light Italic, where 4.93 has
    three loose pieces of the e-shaped outline instead of an outline and a
    counter.  The sign is drawn with hairlines and hardly changes with weight
    (ink: Regular 57,852 units^2, Medium 58,696), and thinning it by the
    Light stem difference (9 units a side) erases the hairlines, so the
    Regular / Italic outline is used as it is.  Only done when the glyph's
    contour count differs from the reference's, so a fixed input is left alone.
    """
    from fontTools.ttLib.tables import ttProgram
    from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
    glyf, ref_glyf = font['glyf'], reference['glyf']
    name, ref_name = font.getBestCmap().get(cp), reference.getBestCmap().get(cp)
    if not name or not ref_name:
        return False
    glyph, ref = glyf[name], ref_glyf[ref_name]
    if glyph.numberOfContours == ref.numberOfContours:
        return False
    coords, flags, contours = _contours(ref, ref_glyf)
    glyph.coordinates = GlyphCoordinates([tuple(p) for p in coords])
    glyph.flags = bytearray(f & 1 for f in flags)
    glyph.endPtsOfContours = [c[-1] for c in contours]
    glyph.numberOfContours = len(contours)
    glyph.program = ttProgram.Program()
    glyph.program.fromBytecode(b'')     # re-hinted later
    glyph.recalcBounds(glyf)
    font['hmtx'][name] = (font['hmtx'][name][0], glyph.xMin)
    return True


def rebuild_light_half(font, reference):
    """Light U+00BD: draw the denominator 2 again from the Light digit 2.

    4.93 Light has the numerator and the bar of the one-half sign, but the
    denominator is 13 points (an angle and a loose foot of the 2), so the
    sign reads "1 / ∠".  The other Light fractions (U+00BC, U+00BE, U+2153)
    and every other weight are fine.  The denominator is the Light digit 2
    scaled into the box a 2 has in the one-half sign: left, right and bottom
    are those of the broken contour (they match the foot of the 2 that is
    left), the top is the Light one-quarter denominator's top plus the
    difference the Regular reference has between its one-half and
    one-quarter denominators.  Only done when the denominator has fewer than
    a third of the reference's points, so a fixed input is left alone.
    """
    from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
    glyf, ref_glyf = font['glyf'], reference['glyf']
    cmap, ref_cmap = font.getBestCmap(), reference.getBestCmap()
    if not all(cp in cmap and cp in ref_cmap for cp in (0xBD, 0xBC, 0x32)):
        return False

    def denominator(g, gl):
        coords, flags, contours = _contours(g, gl)
        low = min(range(len(contours)), key=lambda k: min(coords[i][1] for i in contours[k]))
        return coords, flags, contours, low

    glyph = glyf[cmap[0xBD]]
    coords, flags, contours, low = denominator(glyph, glyf)
    ref_half = denominator(ref_glyf[ref_cmap[0xBD]], ref_glyf)
    if len(contours[low]) * 3 >= len(ref_half[2][ref_half[3]]):
        return False
    top_of = lambda d: max(d[0][i][1] for i in d[2][d[3]])
    quarter = denominator(glyf[cmap[0xBC]], glyf)
    ref_quarter = denominator(ref_glyf[ref_cmap[0xBC]], ref_glyf)
    top = top_of(quarter) + top_of(ref_half) - top_of(ref_quarter)
    old = [coords[i] for i in contours[low]]
    left, right = min(p[0] for p in old), max(p[0] for p in old)
    bottom = min(p[1] for p in old)

    two, two_flags, two_contours = _contours(glyf[cmap[0x32]], glyf)
    if len(two_contours) != 1:
        return False
    tx, ty = [p[0] for p in two], [p[1] for p in two]
    sx = (right - left) / (max(tx) - min(tx))
    sy = (top - bottom) / (max(ty) - min(ty))
    drawn = [(round((x - min(tx)) * sx + left), round((y - min(ty)) * sy + bottom)) for x, y in two]
    drawn_flags = [f & 1 for f in two_flags]

    new_coords, new_flags, ends = [], [], []
    for k, contour in enumerate(contours):
        if k == low:
            new_coords += drawn
            new_flags += drawn_flags
        else:
            new_coords += [tuple(coords[i]) for i in contour]
            new_flags += [flags[i] & 1 for i in contour]
        ends.append(len(new_coords) - 1)
    glyph.coordinates = GlyphCoordinates(new_coords)
    glyph.flags = bytearray(new_flags)
    glyph.endPtsOfContours = ends
    glyph.program = ttProgram.Program()
    glyph.program.fromBytecode(b'')     # re-hinted later
    glyph.recalcBounds(glyf)
    return True
