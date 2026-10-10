#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebuild the Light kanji whose 2.5 outline is broken.

2.5 Light carries 95 kanji with a black wedge, a spur or a missing stroke (共 題 武 昆 廃 慮
...); Regular to Bold have none.  The defect is already in the 2.5 outline, so softening and
widening in build_sans_30.py carry it over.  light_repair.json lists the glyphs (found with
xweight.py on the 2.5 faces; every one looked at by eye: 83 side by side with Regular and
Medium, about 25 of them also as an overlay on Regular).

For each listed glyph the Regular outline of the same family is eroded to Light weight:

    eroded = Regular - stroke(boundary of Regular, width 2 d)

d is searched so that the ink area becomes the area Light has on sound kanji of the same
density (the median Light / Regular area ratio of the 100 sound kanji whose Regular area is
nearest).  Light and Regular share a cell and an origin, so the eroded glyph sits where the
broken one stood.  The advance, the vertical origin and the other tables are not touched.
"""
import json
import os

import pathops
from fontTools.pens.areaPen import AreaPen

HERE = os.path.dirname(os.path.abspath(__file__))
LIST = os.path.join(HERE, "light_repair.json")
NEAREST = 100


def load_list():
    with open(LIST, encoding="utf-8") as fh:
        return json.load(fh)


def _path(gs, name):
    p = pathops.Path()
    gs[name].draw(p.getPen(glyphSet=gs))
    p.simplify(fix_winding=True, keep_starting_points=False, clockwise=True)
    return p


def erode(path, d):
    """Inward offset by d (font units).  Convex corners stay sharp, reflex corners round off."""
    if d <= 0:
        return path
    band = pathops.Path(path)
    band.stroke(2 * d, pathops.LineCap.BUTT_CAP, pathops.LineJoin.ROUND_JOIN, 4)
    band.convertConicsToQuads(0.1)
    band.simplify(fix_winding=True, keep_starting_points=False, clockwise=True)
    return pathops.op(path, band, pathops.PathOp.DIFFERENCE, fix_winding=True,
                      keep_starting_points=False, clockwise=True)


def _area(gs, name):
    pen = AreaPen(gs)
    gs[name].draw(pen)
    return abs(pen.value)


def target_ratios(light, regular, bad):
    """(sorted Regular areas, Light / Regular ratios) of the sound kanji."""
    gl, gr = light.getGlyphSet(), regular.getGlyphSet()
    cm = regular.getBestCmap()
    rows = []
    for cp in range(0x4E00, 0xA000):
        n = cm.get(cp)
        if not n or n in bad or n not in light["glyf"] or regular["glyf"][n].numberOfContours <= 0 \
                or light["glyf"][n].numberOfContours <= 0:
            continue
        a = _area(gr, n)
        rows.append((a, _area(gl, n) / a))
    rows.sort()
    return rows


def ratio_for(rows, area):
    import bisect
    i = bisect.bisect_left([r[0] for r in rows], area)
    lo = max(0, min(i - NEAREST // 2, len(rows) - NEAREST))
    rs = sorted(r[1] for r in rows[lo:lo + NEAREST])
    return rs[len(rs) // 2]


def repaired_glyph(regular_gs, rows, name, tt_glyph):
    """TrueType glyph: Regular's outline of `name` eroded to Light weight."""
    base = _path(regular_gs, name)
    a0 = abs(base.area)
    target = a0 * ratio_for(rows, a0)
    lo, hi = 0.0, 40.0
    for _ in range(14):
        mid = (lo + hi) / 2
        if abs(erode(base, mid).area) > target:
            lo = mid
        else:
            hi = mid
    d = (lo + hi) / 2
    out = erode(base, d)
    out.simplify(fix_winding=True, keep_starting_points=False, clockwise=True)
    return tt_glyph(out), d


def repair(light, regular, tt_glyph):
    """Replace the listed glyphs in `light` (in place).  Returns {glyph: d used}."""
    names = load_list()["glyphs"]
    rows = target_ratios(light, regular, set(names))
    grs = regular.getGlyphSet()
    used = {}
    for n in names:
        assert light["glyf"][n].numberOfContours > 0 and regular["glyf"][n].numberOfContours > 0, n
        light["glyf"][n], used[n] = repaired_glyph(grs, rows, n, tt_glyph)
        used[n] = round(used[n], 2)
    return used
