"""Thicken the Light and LightItalic stems of the 4.93 input.

4.93 Light was made by thinning Regular to a 62-unit stem (Regular 80, Medium 92, SemiBold 104,
Bold 123).  The steps are 18, 12, 12, 19: Light sits 18 below Regular where the other steps are
12, and at 13-24 px it reads grey and thin beside Regular.  This widens Light by LIGHT_GROW units
of stem (the same dilation and zone handling that derive_iosevka_weights.py used to make it), so
the Light-to-Regular step becomes 13-14, near the 12 of the Medium and SemiBold steps.

Edges that sit on a zone (baseline, x-height, cap height, ascender, descender) are put back on
the zone, as in the original derivation, so heights do not move.  Glyphs that Regular, Medium
and Bold draw identically (block elements, shades, Powerline: geometry that tiles the cell) stay
as drawn.
"""
import io
import math
import sys
from pathlib import Path

from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'tools'))
import shapes  # noqa: E402

LIGHT_GROW = 5.0          # stem units: 62 -> 66-67 (Regular 80: step 13-14)


def zone_map(font, d):
    """Piecewise-linear y map that returns zone edges moved by d/2 to the zone."""
    cm, glyf = font.getBestCmap(), font['glyf']

    def edge(ch, top):
        g = glyf[cm[ord(ch)]]
        g.recalcBounds(glyf)
        return g.yMax if top else g.yMin
    zones = sorted({edge('p', False), 0, edge('x', True), edge('H', True), edge('l', True)})
    src, dst = [], []
    for z in zones:
        off = -d / 2 if z <= 0 else d / 2
        src.append(z + off)
        dst.append(z)
    src = [src[0] - 2000] + src + [src[-1] + 2000]
    dst = [dst[0] - 2000] + dst + [dst[-1] + 2000]

    def f(y):
        for i in range(len(src) - 1):
            if src[i] <= y <= src[i + 1]:
                t = (y - src[i]) / (src[i + 1] - src[i])
                return dst[i] + (dst[i + 1] - dst[i]) * t
        return y
    return f


def remap(rec, f):
    return [(op, tuple(None if p is None else (p[0], f(p[1])) for p in args)) for op, args in rec]


def _record(font, name):
    gs = font.getGlyphSet()
    pen = DecomposingRecordingPen(gs)
    gs[name].draw(pen)
    return pen.value


def invariant(inputs, italic):
    """Glyphs drawn the same in Regular, Medium and Bold of the same slant."""
    names = ('Italic', 'MediumItalic', 'BoldItalic') if italic else ('Regular', 'Medium', 'Bold')
    fonts = [TTFont(io.BytesIO(inputs[s][0])) for s in names]
    same = set()
    for name in fonts[0].getGlyphOrder():
        g = fonts[0]['glyf'][name]
        if g.isComposite() or g.numberOfContours <= 0:
            continue
        recs = [_record(f, name) for f in fonts if name in f['glyf']]
        if len(recs) == 3 and recs[0] == recs[1] == recs[2]:
            same.add(name)
    return same


def needles(glyph, glyf):
    """On-curve points that are needle tips: both neighbours within 8-80 units, folded back on
    each other (under ~25 degrees) and closer to each other than half the shorter arm.  The same
    test as spike_check.py.  Returns [(point index, (x, y))]."""
    coords, ends, flags = glyph.getCoordinates(glyf)
    found, start = [], 0
    for end in ends:
        idx = list(range(start, end + 1))
        start = end + 1
        n = len(idx)
        for k in range(n):
            a, p, b = coords[idx[k - 1]], coords[idx[k]], coords[idx[(k + 1) % n]]
            pa, pb = math.dist(a, p), math.dist(p, b)
            if min(pa, pb) < 8 or max(pa, pb) > 80:
                continue
            v1, v2 = (a[0] - p[0], a[1] - p[1]), (b[0] - p[0], b[1] - p[1])
            cos = (v1[0] * v2[0] + v1[1] * v2[1]) / (pa * pb)
            if cos > 0.9 and math.dist(a, b) < 0.5 * min(pa, pb) and flags[idx[k]] & 1:
                found.append((idx[k], (round(p[0]), round(p[1]))))
    return found


def drop_points(glyph, indices):
    """Delete the given points from a simple glyph (descending, so the indices stay valid)."""
    coords, ends, flags = list(glyph.coordinates), list(glyph.endPtsOfContours), list(glyph.flags)
    for i in sorted(indices, reverse=True):
        del coords[i], flags[i]
        ends = [e - 1 if e >= i else e for e in ends]
    from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
    glyph.coordinates = GlyphCoordinates(coords)
    glyph.flags = bytearray(flags) if isinstance(glyph.flags, (bytes, bytearray)) else flags
    glyph.endPtsOfContours = ends


def thicken(font, inputs, italic, grow=LIGHT_GROW):
    """Widen the stems of `font` (a Light face) by `grow` units, in place.  Returns a summary."""
    glyf, hmtx = font['glyf'], font['hmtx']
    fixed = invariant(inputs, italic)
    fy = zone_map(font, grow)
    del shapes.failures[:]
    kept, changed = [], 0
    for name in font.getGlyphOrder():
        g = glyf[name]
        if g.isComposite() or g.numberOfContours <= 0 or name in fixed:
            continue
        rec = _record(font, name)
        if not rec:
            continue
        res, frac = shapes.dilate_graded(rec, grow, name, steps=(1.0, .85, .7, .55, .4))
        if frac < 1.0:
            kept.append([name, frac])
            if not frac:
                continue
        res = remap(res, fy)
        tt = TTGlyphPen(None)
        cu = Cu2QuPen(tt, max_err=0.25, reverse_direction=False)
        for op, args in res:
            getattr(cu, op)(*args)
        new = tt.glyph()
        new.recalcBounds(glyf)
        glyf[name] = new
        hmtx[name] = (hmtx[name][0], getattr(new, 'xMin', 0))
        changed += 1
    for name in font.getGlyphOrder():
        g = glyf[name]
        if g.isComposite():
            g.recalcBounds(glyf)
            hmtx[name] = (hmtx[name][0], g.xMin)
    return {'grow': grow, 'changed': changed, 'kept_part': kept, 'fixed_geometry': len(fixed)}


def trim_needles(font, reference):
    """Remove needle tips that the widening made (and the later height scaling left): points of
    `font` that are needles where `reference` (the 4.93 face) has none within 12 units, in glyphs
    whose spikes were not looked at and found designed (spike_review.py).  Returns [(glyph, n)]."""
    import spike_review
    glyf, rglyf = font['glyf'], reference['glyf']
    cmap_ref = reference.getBestCmap()
    ref_of = {n: cmap_ref[cp] for cp, n in font.getBestCmap().items() if cp in cmap_ref}
    done = []
    for name in font.getGlyphOrder():
        g = glyf[name]
        if g.isComposite() or g.numberOfContours <= 0 or spike_review.reviewed(font, name):
            continue
        was = [pos for _, pos in needles(rglyf[ref_of[name]], rglyf)] if name in ref_of else []
        tips = [i for i, pos in needles(g, glyf) if not any(math.dist(pos, w) < 12 for w in was)]
        if tips:
            drop_points(g, tips)
            g.recalcBounds(glyf)
            done.append([name, len(tips)])
    return done
