#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gaps that 2.5 carried into 3.0 and that build_sans_30.py closes.

  add_approx_equal   U+2252 (≒) is in JIS X 0208 but was in no Friday Sans face; apps fell back
                     to another font.  It is drawn from the face's own ＝ and ． outlines.
  zero_width_like_light  27 combining glyphs (the ...comb / ...subcomb forms) have advance 0 in Light
                     and Regular but 3-104 in SemiBold / Bold (and UI Medium); their outlines hang
                     to the left of the origin, so the advance is a leftover.  Set to 0.
  add_feature_names  ss01-ss08 and cv01-cv14 point at name IDs 276-297 that the name table does
                     not have (the Inter names were lost in the 2.x merge).
  lower_bold_script_g  U+210A (ℊ) sits 214 units too high in 2.5 Bold (it spans -26..765, where
                     every other weight spans -240..564); it is moved down to SemiBold's depth.
"""
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

APPROX = 0x2252
APPROX_NAME = "jp.uni2252"
EQUALS, PERIOD = 0xFF1D, 0xFF0E
DOT_OVER_BAR = 1.45       # dot diameter / bar thickness
DOT_GAP = 0.55            # gap between dot and bar / bar thickness


def _contour_boxes(glyph, glyf):
    coords, ends, _ = glyph.getCoordinates(glyf)
    boxes, start = [], 0
    for e in ends:
        pts = coords[start:e + 1]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
        start = e + 1
    return boxes


def add_approx_equal(f):
    """Add ≒: ＝ with a dot above the left end of the upper bar and one below the right end of
    the lower bar (the Japanese form: Yu Gothic, Meiryo and MS Gothic draw it so; ≓ is the
    mirror).  Returns the glyph name, or None when the face already has U+2252."""
    cm = f.getBestCmap()
    if APPROX in cm:
        return None
    glyf, gs = f["glyf"], f.getGlyphSet()
    eq, dot = cm[EQUALS], cm[PERIOD]
    bars = sorted(_contour_boxes(glyf[eq], glyf), key=lambda b: b[1])
    assert len(bars) == 2, bars
    lo, hi = bars
    t = (lo[3] - lo[1] + hi[3] - hi[1]) / 2.0
    x0, x1 = min(lo[0], hi[0]), max(lo[2], hi[2])
    (dx0, dy0, dx1, dy1), = _contour_boxes(glyf[dot], glyf)
    d = DOT_OVER_BAR * t
    k = d / max(dx1 - dx0, dy1 - dy0)
    gap = DOT_GAP * t

    pen = TTGlyphPen(None)
    gs[eq].draw(pen)

    def place(left, bottom):
        # scale the period about its own box corner, then move that corner to (left, bottom)
        gs[dot].draw(TransformPen(pen, (k, 0, 0, k, left - dx0 * k, bottom - dy0 * k)))

    place(x0, hi[3] + gap)                  # above the left end of the upper bar
    place(x1 - (dx1 - dx0) * k, lo[1] - gap - (dy1 - dy0) * k)   # below the right end of the lower bar
    g = pen.glyph()
    g.recalcBounds(glyf)

    order = f.getGlyphOrder()
    assert APPROX_NAME not in order
    glyf[APPROX_NAME] = g
    adv, _ = f["hmtx"][eq]
    f["hmtx"][APPROX_NAME] = (adv, g.xMin)
    vadv, tsb = f["vmtx"][eq]
    f["vmtx"][APPROX_NAME] = (vadv, tsb + glyf[eq].yMax - g.yMax)    # same vertical origin as ＝
    for t_ in f["cmap"].tables:
        if t_.isUnicode() and t_.format in (4, 12):
            t_.cmap[APPROX] = APPROX_NAME
    return APPROX_NAME


# Inter 4.0's own names for these features (name IDs 276-297 of reference/Inter/Inter-Variable
# Font; the IDs are the same ones the 2.x merge kept in FeatureParams).
FEATURE_NAMES = {
    "ss01": "Open digits",
    "ss02": "Disambiguation",
    "ss03": "Round quotes & commas",
    "ss04": "Disambiguation (no slashed zero)",
    "ss05": "Circled characters",
    "ss06": "Squared characters",
    "ss07": "Square punctuation",
    "ss08": "Square quotes",
    "cv01": "Alternate one",
    "cv02": "Open four",
    "cv03": "Open six",
    "cv04": "Open nine",
    "cv05": "Lower-case L with tail",
    "cv06": "Simplified u",
    "cv07": "Alternate sharp s",
    "cv08": "Upper-case i with serif",
    "cv09": "Flat-top three",
    "cv10": "Capital G with spur",
    "cv11": "Single-story a",
    "cv12": "Compact f",
    "cv13": "Compact t",
    "cv14": "Alternate capital sharp S",
}


def add_feature_names(f):
    """Give every FeatureParams name ID that the name table lacks a name.  Returns {id: text}."""
    have = {r.nameID for r in f["name"].names}
    added = {}
    for tag in ("GSUB", "GPOS"):
        if tag not in f:
            continue
        for rec in f[tag].table.FeatureList.FeatureRecord:
            p = rec.Feature.FeatureParams
            if p is None or rec.FeatureTag not in FEATURE_NAMES:
                continue
            nid = getattr(p, "UINameID", None) or getattr(p, "FeatUILabelNameID", None)
            if nid and nid not in have and nid not in added:
                added[nid] = FEATURE_NAMES[rec.FeatureTag]
    for nid, text in added.items():
        f["name"].setName(text, nid, 3, 1, 0x409)
    return added


SCRIPT_G = "jp.uni210A"


def lower_bold_script_g(f, semibold):
    """Move Bold's ℊ down so its bottom is where SemiBold's is.  Returns the shift (0 if none)."""
    glyf = f["glyf"]
    g, ref = glyf[SCRIPT_G], semibold["glyf"][SCRIPT_G]
    g.recalcBounds(glyf)
    dy = ref.yMin - g.yMin
    if abs(dy) <= 20 * f["head"].unitsPerEm / 1000.0:
        return 0
    g.coordinates.translate((0, dy))
    g.recalcBounds(glyf)
    return dy


def classify_zero_width_marks(f):
    """Put zero-advance combining glyphs into the GDEF mark class.  Inter's combining marks and
    the Cyrillic enclosing marks U+0488 / U+0489 had no class after the 2.x merge, so a layout
    engine took them for base glyphs of width 0 (Fontspector: base_has_width).  Only glyphs of
    zero advance with an outline are touched: spacing marks (the CJK tone marks) must keep
    their width, and HarfBuzz zeroes the advance of every glyph in the mark class."""
    import unicodedata
    gdef = f["GDEF"].table
    if gdef.GlyphClassDef is None:
        return []
    classes = gdef.GlyphClassDef.classDefs
    cmap = {n: cp for cp, n in f.getBestCmap().items()}
    done = []
    for n in f.getGlyphOrder():
        if classes.get(n) == 3 or f["hmtx"][n][0] != 0 or f["glyf"][n].numberOfContours == 0:
            continue
        cp = cmap.get(n)
        is_mark = (cp is not None and unicodedata.category(chr(cp)) in ("Mn", "Me")) or n.endswith("comb")
        if is_mark:
            classes[n] = 3
            done.append(n)
    return done


def zero_width_like_light(f, light):
    """Advance 0 for the glyphs that are zero-width marks in Light (and have an outline).
    Returns {glyph: old advance} for the ones changed."""
    done = {}
    lg, lh = light["glyf"], light["hmtx"]
    for n in f.getGlyphOrder():
        if n in lg and lg[n].numberOfContours > 0 and lh[n][0] == 0 and f["hmtx"][n][0] != 0                 and f["glyf"][n].numberOfContours > 0:
            done[n] = f["hmtx"][n][0]
            f["hmtx"][n] = (0, f["hmtx"][n][1])
    return done
