"""Repair the faceted extrema that the 4.9x Latin build left in Friday Mono.

The 4.9x outlines reach the top and bottom of round letters through a short
polyline: on-curve, duplicate on-curve, the extremum, on-curve, duplicate.
ttfautohint reads those tops as flat, puts the cap and x-height blue zones at
the round overshoot (745 / 530) instead of the flat height (737 / 522), and
then rounds O C G S o c e s one pixel taller than H x at almost every text
size.  That is the "C is too big" report.

The repair keeps every on-curve extremum where it is and only:

1. drops on-curve points that repeat (or sit within 1.5 units of) the previous
   on-curve point;
2. turns each extremum "tent" (on, on-extremum, on, between off-curve points)
   into two quadratic arcs with a horizontal (or vertical) tangent at the
   extremum.  The new control point continues the incoming tangent where that
   lands between the neighbour and the extremum, so the joint stays smooth.

Bounding boxes, advances and every point other than those listed are kept.
"""
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphCoordinates
from fontTools.ttLib.tables import ttProgram

NEAR = 1
PAIR = 6
TENT = 15
MERGE_TOLERANCE = 3.0


def _contours(glyph, glyf):
    coords, ends, flags = glyph.getCoordinates(glyf)
    out, start = [], 0
    for end in ends:
        out.append([[coords[i][0], coords[i][1], flags[i] & 1]
                    for i in range(start, end + 1)])
        start = end + 1
    return out


def _dedupe(points, box=None):
    changed = 0
    while True:
        n = len(points)
        drop = None
        for i in range(n):
            a, b = points[i - 1], points[i]
            if a[2] and b[2] and abs(a[0] - b[0]) <= NEAR and abs(a[1] - b[1]) <= NEAR and n > 3:
                if a[:2] == b[:2] or box is None or _covers(a, b, box):
                    drop = i
                elif _covers(b, a, box):
                    drop = i - 1 if i else n - 1
                else:
                    continue
                break
            if not a[2] and not b[2] and a[0] == b[0] and a[1] == b[1] and n > 3:
                drop = i
                break
            # an on-curve point on the straight line between its on-curve
            # neighbours (within COLLINEAR units) adds nothing to the shape;
            # left in, the vertical scale and emboldening of the SF Mono
            # heights bend it into a needle (A, V in Bold Italic) or a stray
            # edge in the cap zone (the apex of 4 and 7 in Light Italic)
            c = points[(i + 1) % n]
            if a[2] and b[2] and c[2] and n > 4 and _between(a, b, c):
                drop = i
                break
            # two on-curve points side by side at a local extremum (c e s bottoms)
            if a[2] and b[2] and n > 5 and abs(a[1] - b[1]) <= 1 and 0 < abs(a[0] - b[0]) <= PAIR:
                before, after = points[i - 2], points[(i + 1) % n]
                side = before[1] - a[1]
                # only inside curves: an off-curve point within two places on
                # both sides (keeps the flat crotch of X and the flag joint of 1)
                curved = (not before[2] or not points[i - 3][2]) and                     (not after[2] or not points[(i + 2) % n][2])
                if curved and side * (after[1] - b[1]) > 0:
                    # keep the point that reaches further (the extremum)
                    worse_b = (b[1] - a[1]) * side > 0
                    drop = i if worse_b or a[1] == b[1] else (i - 1 if i else n - 1)
                    break
        if drop is None:
            return points, changed
        points.pop(drop)
        changed += 1


COLLINEAR = 0.5


def _between(a, b, c, tolerance=None):
    """b lies on the straight line a-c (within COLLINEAR units), between them."""
    tolerance = COLLINEAR if tolerance is None else tolerance
    dx, dy = c[0] - a[0], c[1] - a[1]
    length2 = dx * dx + dy * dy
    if not length2:
        return False
    t = ((b[0] - a[0]) * dx + (b[1] - a[1]) * dy) / length2
    if not 0 < t < 1:
        return False
    return abs((b[0] - a[0]) * dy - (b[1] - a[1]) * dx) / length2 ** 0.5 <= tolerance


def _covers(keep, drop, box):
    """True when dropping `drop` cannot shrink the bounding box: `keep` lies
    on every box edge that `drop` lies on."""
    return all(keep[axis] == edge for axis, edge in
               ((0, box[0]), (1, box[1]), (0, box[2]), (1, box[3])) if drop[axis] == edge)


def _quad(p0, p1, p2, steps=16):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])
            for t in (k / steps for k in range(steps + 1))]


def _merge_arc(q, off, a, p, axis):
    """One quadratic q -> c -> p replacing q -> off -> a, a -> p.

    c is where the tangent at q (towards off) meets the extremum line, so the
    joint at q keeps its direction and the extremum keeps a flat tangent.
    Returns None when that control falls outside q..p or the new arc strays
    more than MERGE_TOLERANCE units from the old path.
    """
    other = 1 - axis
    d = off[axis] - q[axis]
    if not d:
        return None
    t = (p[axis] - q[axis]) / d
    if t <= 0:
        return None
    c = [0, 0, 0]
    c[axis] = p[axis]
    c[other] = q[other] + t * (off[other] - q[other])
    lo, hi = sorted((q[other], p[other]))
    if not lo < c[other] < hi:
        return None
    old = _quad(q, off, a) + [(a[0] + (p[0] - a[0]) * k / 8, a[1] + (p[1] - a[1]) * k / 8) for k in range(9)]
    new = _quad(q, c, p, 64)
    error = max(min((x - u) ** 2 + (y - v) ** 2 for u, v in new) for x, y in old) ** 0.5
    if error > MERGE_TOLERANCE:
        return None
    c[other] = round(c[other])
    return c


def _control(prev_off, a, p, axis):
    """Control point between a and the extremum p on the line axis == p[axis]."""
    other = 1 - axis
    lo, hi = sorted((a[other], p[other]))
    mid = (a[other] + p[other]) / 2
    da = a[axis] - prev_off[axis]
    if da:
        t = (p[axis] - a[axis]) / da
        cand = a[other] + t * (a[other] - prev_off[other])
        if lo + 0.15 * (hi - lo) <= cand <= hi - 0.15 * (hi - lo):
            mid = cand
    pt = [0, 0, 0]
    pt[axis] = p[axis]
    pt[other] = round(mid)
    return pt


def _fix_tents(points, axes):
    fixed = 0
    i = 0
    while i < len(points):
        n = len(points)
        a, p, b = points[i - 1], points[i], points[(i + 1) % n]
        pa, bn = points[i - 2], points[(i + 2) % n]
        rotated = False
        if a[2] and p[2] and b[2] and not pa[2] and not bn[2] and n >= 5:
            for axis in axes:
                other = 1 - axis
                up = p[axis] > a[axis] and p[axis] > b[axis]
                down = p[axis] < a[axis] and p[axis] < b[axis]
                if not (up or down):
                    continue
                if abs(p[axis] - a[axis]) > TENT or abs(p[axis] - b[axis]) > TENT:
                    continue
                if abs(p[other] - a[other]) <= abs(p[axis] - a[axis]):
                    continue
                if abs(p[other] - b[other]) <= abs(p[axis] - b[axis]):
                    continue
                qa, qb = points[i - 3], points[(i + 3) % n]
                m1 = _merge_arc(qa, pa, a, p, axis) if axis == 1 and qa[2] and n >= 7 else None
                m2 = _merge_arc(qb, bn, b, p, axis) if axis == 1 and qb[2] and n >= 7 else None
                c1 = m1 or _control(pa, a, p, axis)
                c2 = m2 or _control(bn, b, p, axis)
                # rebuild the run [i-2 .. i+2] around the extremum
                left = [c1] if m1 else [pa, a, c1]
                right = [c2] if m2 else [c2, b, bn]
                idx = [(i + k) % n for k in range(-2, 3)]
                run = left + [p] + right
                keep = [pt for j, pt in enumerate(points) if j not in idx]
                start = min(idx) if max(idx) - min(idx) == 4 else None
                if start is None:            # run wraps the contour end: rotate first
                    k = (i - 2) % n
                    points[:] = points[k:] + points[:k]
                    i = 2
                    rotated = True
                    break
                points[:] = keep[:start] + run + keep[start:]
                fixed += 1
                i = start + len(run) - 1
                break
        if rotated:
            continue
        i += 1
    return fixed


def repair_glyph(glyph, glyf, axes=(1,)):
    """Return (dropped points, repaired tents). Rewrites a simple glyph in place."""
    if glyph.numberOfContours <= 0:
        return 0, 0
    contours = _contours(glyph, glyf)
    box = (glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax)
    dropped = tents = 0
    for points in contours:
        _, d = _dedupe(points, box)
        dropped += d
        tents += _fix_tents(points, axes)
    if not dropped and not tents:
        return 0, 0
    coords, flags, ends = [], [], []
    for points in contours:
        for x, y, on in points:
            coords.append((x, y))
            flags.append(1 if on else 0)
        ends.append(len(coords) - 1)
    glyph.coordinates = GlyphCoordinates(coords)
    glyph.flags = bytearray(flags)
    glyph.endPtsOfContours = ends
    program = ttProgram.Program()
    program.fromBytecode(b"")
    glyph.program = program
    glyph.recalcBounds(glyf)
    return dropped, tents


def count_tents(glyph, glyf, axes=(1,)):
    if glyph.numberOfContours <= 0:
        return 0
    total = 0
    for points in _contours(glyph, glyf):
        points, _ = _dedupe(points)
        n = len(points)
        for i in range(n):
            a, p, b = points[i - 1], points[i], points[(i + 1) % n]
            pa, bn = points[i - 2], points[(i + 2) % n]
            if not (a[2] and p[2] and b[2]) or pa[2] or bn[2]:
                continue
            for axis in axes:
                other = 1 - axis
                if ((p[axis] > a[axis] and p[axis] > b[axis]) or (p[axis] < a[axis] and p[axis] < b[axis])) \
                        and abs(p[axis] - a[axis]) <= TENT and abs(p[axis] - b[axis]) <= TENT \
                        and abs(p[other] - a[other]) > abs(p[axis] - a[axis]) \
                        and abs(p[other] - b[other]) > abs(p[axis] - b[axis]):
                    total += 1
    return total
