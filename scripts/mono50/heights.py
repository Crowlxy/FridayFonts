"""Bring Friday Mono's vertical proportions to SF Mono's.

SF Mono Regular (measured, docs/DESIGN.md 2.1): x-height 528.8, cap 704.6,
`l` 738 -> cap / x = 1.3325, ascender / cap = 1.047.  Friday 4.93 keeps
Iosevka's 737 / 522 = 1.412 (and digits at 745), so its capitals look large
next to lowercase.  The x-height stays; everything tied to the cap height or
the ascender comes down:

  cap      capitals, cap-height symbols              scale from the baseline
  digits   0-9 (4.93: 745 / -10, above H)            flat ends to H, round to O
  asc      lowercase with ascenders                  compress above x-height
  sym      ( ) [ ] { } | / \\ section dagger ...      scale about the math axis
  raised   quotes, degree, superscripts, ...         move with the cap height
  dot      the dot of i and j                        move down DOT_SHIFT

Scaling a stroke vertically thins its horizontal parts, so every scaled
contour is emboldened in y only by exactly what the scale took away
(FreeType's FT_Outline_EmboldenXY with xstrength 0).  Vertical stems, widths
and side bearings do not change.  Contours that sit wholly above the body
(accents, the ring of A, the hook of d-caron) are moved rigidly with the body
top, so their size and their gap to the letter are kept.

Every glyph gets a mapping for y; `anchor_map` applies the same mapping to
mark-attachment anchors in GPOS.
"""
import math
import unicodedata as ud

from fontTools.agl import toUnicode

SF_CAP_PER_X = 704.6 / 528.8
SF_ASC_PER_CAP = 738.0 / 704.6
MATH_AXIS = 340             # centre of Friday's math operators and brackets
ASC_MIN = 690               # lowest stem top counted as an ascender (horns: ~640)
LIFTED = 755                # 4.93's lifted ascenders (l b d f h k: 772)
DOT_SHIFT = -20             # i / j dot: keeps it within the references' range
BOX = (0x2500, 0x259F)
CAP_SYMBOLS = set(map(ord, '!?%&#@$¶')) | {0x2116, 0x2030}
DOTTED = {0x69, 0x6A, 0x12F, 0x1ECB, 0x1E2D, 0x456, 0x458, 0x3F3}
STEP_LEVEL = 5              # font units: points this close to a flat digit end are put on it
# (top flat, bottom flat), from the design (checked at 300 px): 6 and 9 end
# in a cut stroke, the others are flat bars and stems or curves
DIGIT_ENDS = {'0': (False, False), '1': (True, True), '2': (False, True), '3': (False, False),
              '4': (True, True), '5': (True, False), '6': (True, False), '7': (True, True),
              '8': (False, False), '9': (False, True)}


def _codepoint(name, reverse):
    if name in reverse:
        return reverse[name]
    base = name.split('.')[0]
    if base in reverse:
        return reverse[base]
    text = toUnicode(base)
    return ord(text) if len(text) == 1 else None


def _contours(glyph, glyf):
    coords, ends, flags = glyph.getCoordinates(glyf)
    out, start = [], 0
    for end in ends:
        out.append(list(range(start, end + 1)))
        start = end + 1
    return coords, flags, out


def _measure(font, ch, x):
    """Vertical ink runs of `ch` on the line x (font units)."""
    from fontTools.pens.recordingPen import RecordingPen
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
    from scanline import flatten, spans_v
    pen = RecordingPen()
    font.getGlyphSet()[font.getBestCmap()[ord(ch)]].draw(pen)
    return spans_v(flatten(pen.value), x)


def style_targets(font):
    glyf, cmap = font['glyf'], font.getBestCmap()

    def top(ch):
        g = glyf[cmap[ord(ch)]]
        g.recalcBounds(glyf)
        return g.yMax
    x, cap, asc = top('x'), top('H'), top('l')
    g = glyf[cmap[ord('H')]]
    cap_bottom = g.yMin
    runs = [b - a for a, b in _measure(font, 'H', 300)]
    stroke = min(runs)                         # the crossbar of H
    new_cap = x * SF_CAP_PER_X
    new_asc = new_cap * SF_ASC_PER_CAP
    k1 = (new_cap - stroke) / (cap - stroke)
    return {'x_height': x, 'cap': cap, 'ascender': asc, 'stroke': stroke,
            'new_cap': new_cap, 'new_ascender': new_asc,
            'cap_scale': k1, 'cap_embolden': stroke * (1 - k1),
            'asc_base': x + 20, 'cap_bottom': cap_bottom}


def orientation(points, contours):
    """+1 when the glyph's outline is clockwise (TrueType), -1 otherwise.

    Like FT_Outline_Get_Orientation, decided once for the whole glyph from
    the summed signed area: some 4.9x glyphs (the digits) run the other way.
    """
    total = 0.0
    for contour in contours:
        pts = [points[i] for i in contour]
        total += sum(pts[k - 1][0] * pts[k][1] - pts[k][0] * pts[k - 1][1] for k in range(len(pts)))
    return 1 if total < 0 else -1


def embolden_y(points, contour, strength, mask, sense=1):
    """Thicken one contour vertically by `strength` (top faces up, bottoms stay).

    The outline is swept by a vertical segment of length `strength`: a point
    whose outward normal faces up moves the full amount, one facing down
    stays, and points with a near-vertical tangent (|normal y| < BAND) are
    blended so curves stay smooth.  The tangent comes from the neighbouring
    distinct points, so clusters of points a unit or two apart (the end of the
    hook of f) move together.  FreeType's FT_Outline_EmboldenXY was tried
    first; its short-segment limiter lifted single points of such clusters
    by up to 18 units in Bold.

    `sense` is the glyph's orientation (+1 TrueType / clockwise).  Only
    points whose index is in `mask` move.  Returns new (x, y) per index.
    """
    n = len(contour)
    pts = [points[i] for i in contour]
    out = {}
    for j in range(n):
        p = pts[j]
        k = 1
        while k < n and math.dist(pts[(j - k) % n], p) < 0.5:
            k += 1
        prev = pts[(j - k) % n]
        k = 1
        while k < n and math.dist(pts[(j + k) % n], p) < 0.5:
            k += 1
        nxt = pts[(j + k) % n]
        tx, ty = nxt[0] - prev[0], nxt[1] - prev[1]
        length = math.hypot(tx, ty)
        if not length or contour[j] not in mask:
            out[contour[j]] = p
            continue
        normal_y = sense * tx / length          # outward normal, y component
        weight = min(max((normal_y + BAND) / (2 * BAND), 0.0), 1.0)
        out[contour[j]] = (p[0], p[1] + strength * weight)
    return out


BAND = 0.2


class Plan:
    """The y mapping of one glyph."""

    def __init__(self, kind, **params):
        self.kind = kind
        self.__dict__.update(params)

    def anchor(self, y):
        if self.kind == 'cap' and hasattr(self, 'shift'):
            return self.shift + self.scale * y if y > 0 else y
        if self.kind == 'cap':
            if y >= self.top:
                return y + self.delta
            return y * self.new_top / self.top if y > 0 else y
        if self.kind == 'asc':
            if y >= self.top:
                return y + self.delta
            if y > self.base:
                return self.base + (y - self.base) * (self.top + self.delta - self.base) / (self.top - self.base)
            return y
        if self.kind == 'sym':
            return MATH_AXIS + (y - MATH_AXIS) * self.ratio
        if self.kind in ('raised', 'dot'):
            return y + self.delta if (self.kind == 'raised' or y >= self.base) else y
        return y


def _digit_plan(cp, coords, contours, slant, t):
    """A digit's own scale: flat ends land on H, round ends on O.

    4.93 draws every digit from -10 to 745, the overshoot of O, so the flat
    top of 1 4 5 7 stood 8 units above H and the flat foot of 1 2 4 7 8 units
    below it.  ttfautohint snapped them back at text sizes, but at display
    sizes the digits were taller than the capitals.  Which end is flat comes
    from DIGIT_ENDS: the 4.93 outlines draw curves as facets (the top of 0 is
    a 116-unit on-curve run), so ttfautohint's geometric test gives different
    answers in different weights.  The digit is scaled from its bottom to its
    top so both ends reach their targets, and emboldened in y like the
    capitals.
    """
    pts = [(x - y * slant, y) for x, y in coords]
    points = [i for c in contours for i in c]
    hi = max(pts[i][1] for i in points)
    lo = min(pts[i][1] for i in points)
    top_flat, bottom_flat = DIGIT_ENDS[chr(cp)]
    # a flat end is levelled: 4.93 ends some of them in a 4-unit step (the
    # foot of 7, the apex of 4), which the scale turns into a slope that
    # ttfautohint does not take for a baseline or cap-height edge
    level = {}
    k1, e1, s = t['cap_scale'], t['cap_embolden'], t['stroke']
    T = k1 * t['cap'] + e1 if top_flat else k1 * hi + e1
    B = k1 * t['cap_bottom'] if bottom_flat else k1 * lo
    k = (T - B - s) / (hi - lo - s)
    shift = B - k * lo
    for i in points:
        if top_flat and pts[i][1] >= hi - STEP_LEVEL:
            level[i] = T
        elif bottom_flat and pts[i][1] <= lo + STEP_LEVEL:
            level[i] = B
    return Plan('cap', top=hi, body=list(range(len(contours))), new_top=T, delta=T - hi,
                scale=k, shift=shift, embolden=s * (1 - k), flat=(top_flat, bottom_flat), level=level)


def classify(font, t):
    """Return {glyph name: Plan} for every glyph whose heights change."""
    glyf = font['glyf']
    reverse = {}
    for cp, name in font.getBestCmap().items():
        reverse.setdefault(name, cp)
    plans = {}
    asc_ref = None
    for name in font.getGlyphOrder():
        g = glyf[name]
        if g.numberOfContours <= 0:
            continue
        cp = _codepoint(name, reverse)
        if cp is None or BOX[0] <= cp <= BOX[1]:
            continue
        cat = ud.category(chr(cp))
        coords, flags, contours = _contours(g, glyf)
        ys = [[coords[i][1] for i in c] for c in contours]
        lo, hi = min(map(min, ys)), max(map(max, ys))
        if 0x30 <= cp <= 0x39:
            plans[name] = _digit_plan(cp, coords, contours, slant_of(font), t)
        elif cat in ('Lu', 'Lt', 'Nd') or cp in CAP_SYMBOLS or (
                cat in ('Sc', 'No') and -130 <= lo <= 20 and 700 <= hi <= 760):
            # the body: contours that start below the cap height
            body = [i for i, y in enumerate(ys) if min(y) < t['cap'] - 20]
            top = max(max(ys[i]) for i in body)
            plans[name] = Plan('cap', top=top, body=body, new_top=t['cap_scale'] * top + t['cap_embolden'],
                               delta=t['cap_scale'] * top + t['cap_embolden'] - top)
        elif cat == 'Ll' and hi > t['x_height'] + 60 and cp not in DOTTED:
            base = t['asc_base']
            body = [i for i, y in enumerate(ys) if min(y) < base]
            top = max(max(ys[i]) for i in body)
            # the stem's flat top, not a caron hook joined to it (d-caron in
            # SemiBold rises to 767 over a 737 stem)
            flats = [coords[a][1] for i in body for a, b in zip(contours[i], contours[i][1:] + contours[i][:1])
                     if abs(coords[a][1] - coords[b][1]) <= 1 and abs(coords[a][0] - coords[b][0]) >= 20
                     and coords[a][1] > base]
            if flats and max(flats) >= top - 40:
                top = max(flats)
            letter = ud.normalize('NFD', chr(cp))[0]
            # full ascenders, plus t and its accented forms; a horn (o-horn,
            # u-horn) or an accent sitting on an x-height letter stays
            if top < ASC_MIN and letter not in 'tŧ':
                continue
            plans[name] = Plan('asc', top=top, base=base, body=body, t_like=letter in 'tŧ')
        elif cp in DOTTED:
            plans[name] = Plan('dot', base=t['asc_base'], delta=DOT_SHIFT)
        elif cat in ('Ps', 'Pe', 'Po', 'Sm', 'So', 'Pd') and lo < -80 and hi > 790:
            plans[name] = Plan('sym')
        elif (cat in ('Po', 'Pi', 'Pf', 'So', 'No', 'Lo', 'Lm') or cp == 0x5E) and lo >= 250 and hi >= 690 \
                and not 0x2B0 <= cp <= 0x2FF:
            plans[name] = Plan('raised', top=hi, delta=None)
    # ascender targets: full-height ascenders land on the new ascender, shorter
    # ones (t) follow the mapping of l
    # 4.93 has two ascender heights: the lifted one of l b d f h k (772) and
    # Iosevka's own (737: l-stroke, l-caron, h-bar, eszett, beta, be ...).
    # Both land on the new ascender; t and anything between follow l.
    l_plan = plans[font.getBestCmap()[ord('l')]]
    for plan in plans.values():
        if plan.kind == 'asc':
            if plan.top >= LIFTED:
                ref_top = plan.top
            elif plan.top >= ASC_MIN and not plan.t_like:
                ref_top = max(plan.top, t['new_ascender'] + 1)
            else:
                ref_top = l_plan.top
            target_ref = t['new_ascender']
            stroke = t['stroke']
            k2 = (target_ref - plan.base - stroke) / (ref_top - plan.base - stroke)
            plan.scale, plan.embolden = k2, stroke * (1 - k2)
            plan.delta = plan.base + k2 * (plan.top - plan.base) + plan.embolden - plan.top
        elif plan.kind == 'raised':
            plan.delta = plan.top * (t['new_cap'] / t['cap']) - plan.top
    # brackets: top of ( ) goes to new ascender + its old overshoot of the ascender
    paren = plans.get(font.getBestCmap()[ord('(')])
    if paren:
        g = glyf[font.getBestCmap()[ord('(')]]
        g.recalcBounds(glyf)
        target = t['new_ascender'] + (g.yMax - t['ascender'])
        stroke = t['stroke']
        # c + k (top - c) + e / 2 = target, with e = stroke (1 - k)
        k = (target - MATH_AXIS - stroke / 2) / (g.yMax - MATH_AXIS - stroke / 2)
        for plan in plans.values():
            if plan.kind == 'sym':
                plan.scale, plan.embolden = k, stroke * (1 - k)
                plan.ratio = (target - MATH_AXIS) / (g.yMax - MATH_AXIS)
    return plans


STEP = 10


def _keep_short_steps(old, new, flags, contours, scale):
    """Give short vertical steps their scaled length back after emboldening.

    The apex of 4 and the terminal of 6 end in a 4-unit vertical step.
    Emboldening moves its two ends by different amounts (a corner of a
    diagonal against a flat top) and stretches it to 7 units, which puts the
    lower end on the cap height and lets ttfautohint snap it there, a pixel
    off the other digits.  The outer end stays; the inner end is put back at
    the old distance times the scale.
    """
    mid = (min(y for _, y in old) + max(y for _, y in old)) / 2
    for contour in contours:
        for k in range(len(contour)):
            a, b = contour[k - 1], contour[k]
            if not (flags[a] & 1 and flags[b] & 1):
                continue
            dy = abs(old[a][1] - old[b][1])
            # vertical, or slanted by the italic angle (tan 10 deg = 0.18)
            if not 0 < dy <= STEP or abs(old[a][0] - old[b][0]) > 0.3 * dy:
                continue
            upper = old[a][1] > mid
            outer, inner = (a, b) if (old[a][1] > old[b][1]) == upper else (b, a)
            # only a step that ends in a flat top or bottom (the apex of 4):
            # the outer point's other neighbour lies on its level
            ring = contour
            pos = ring.index(outer)
            other = ring[(pos + 1) % len(ring)] if ring[pos - 1] == inner else ring[pos - 1]
            if abs(old[other][1] - old[outer][1]) > 1 or abs(old[other][0] - old[outer][0]) < 20:
                continue
            gap = old[outer][1] - old[inner][1]
            new[inner] = (new[inner][0], new[outer][1] - gap * scale)


def slant_of(font):
    return math.tan(math.radians(-font['post'].italicAngle))


def apply(font, plans, t):
    glyf = font['glyf']
    slant = slant_of(font)
    for name, plan in plans.items():
        g = glyf[name]
        coords, flags, contours = _contours(g, glyf)
        # work upright: scaling a slanted glyph in y would change its angle,
        # and an accent moved down has to follow the slant
        pts = [(x - y * slant, y) for x, y in coords]
        new = list(pts)
        sense = orientation(pts, contours)
        for ci, contour in enumerate(contours):
            if plan.kind == 'cap':
                if max(pts[i][1] for i in contour) <= 0:
                    continue                  # an accent below (dot, comma): keep
                if ci in plan.body:
                    k = getattr(plan, 'scale', t['cap_scale'])
                    shift = getattr(plan, 'shift', 0)
                    scaled = {i: (pts[i][0], shift + pts[i][1] * k) for i in contour}
                    tmp = list(new)
                    for i, p in scaled.items():
                        tmp[i] = p
                    moved = embolden_y(tmp, contour, getattr(plan, 'embolden', t['cap_embolden']),
                                       set(contour), sense)
                    for i, p in moved.items():
                        new[i] = p
                else:
                    lowest = min(pts[i][1] for i in contour)
                    dy = plan.delta if lowest >= plan.top - 20 else 0
                    for i in contour:
                        new[i] = (pts[i][0], pts[i][1] + dy)
            elif plan.kind == 'asc':
                if ci in plan.body:
                    above = {i for i in contour if pts[i][1] > plan.base}
                    tmp = list(new)
                    for i in contour:
                        y = pts[i][1]
                        tmp[i] = (pts[i][0], plan.base + (y - plan.base) * plan.scale if i in above else y)
                    moved = embolden_y(tmp, contour, plan.embolden, above, sense)
                    for i, p in moved.items():
                        new[i] = p
                else:
                    for i in contour:
                        new[i] = (pts[i][0], pts[i][1] + plan.delta)
            elif plan.kind == 'sym':
                tmp = list(new)
                for i in contour:
                    tmp[i] = (pts[i][0], MATH_AXIS + (pts[i][1] - MATH_AXIS) * plan.scale)
                moved = embolden_y(tmp, contour, plan.embolden, set(contour), sense)
                for i, p in moved.items():
                    new[i] = (p[0], p[1] - plan.embolden / 2)
            elif plan.kind == 'dot':
                if min(pts[i][1] for i in contour) >= plan.base:
                    for i in contour:
                        new[i] = (pts[i][0], pts[i][1] + plan.delta)
            elif plan.kind == 'raised':
                for i in contour:
                    new[i] = (pts[i][0], pts[i][1] + plan.delta)
        scale = {'cap': getattr(plan, 'scale', t['cap_scale']), 'asc': getattr(plan, 'scale', 1),
                 'sym': getattr(plan, 'scale', 1)}.get(plan.kind)
        if scale:
            _keep_short_steps(pts, new, flags, contours, scale)
        for i, y in getattr(plan, 'level', {}).items():
            new[i] = (new[i][0], y)
        for i, (x, y) in enumerate(new):
            y = round(y)
            g.coordinates[i] = (round(x + y * slant), y)
        g.recalcBounds(glyf)
    # composite glyphs follow their components; nothing else to do
    return len(plans)


def move_anchors(font, plans):
    """Apply each base glyph's y mapping to its mark-attachment anchors."""
    if 'GPOS' not in font:
        return 0
    moved = 0
    slant = slant_of(font)
    for lookup in font['GPOS'].table.LookupList.Lookup:
        for sub in lookup.SubTable:
            kind = lookup.LookupType
            if kind == 9:                           # extension: unwrap
                kind, sub = sub.ExtensionLookupType, sub.ExtSubTable
            if kind == 4:                           # mark-to-base
                for name, record in zip(sub.BaseCoverage.glyphs, sub.BaseArray.BaseRecord):
                    plan = plans.get(name)
                    if not plan:
                        continue
                    for anchor in record.BaseAnchor:
                        if anchor is not None:
                            y = round(plan.anchor(anchor.YCoordinate))
                            anchor.XCoordinate = round(anchor.XCoordinate + (y - anchor.YCoordinate) * slant)
                            anchor.YCoordinate = y
                            moved += 1
    return moved


def summary(plans):
    kinds = {}
    for plan in plans.values():
        kinds[plan.kind] = kinds.get(plan.kind, 0) + 1
    return kinds
