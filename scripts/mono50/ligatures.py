"""Coding ligatures for Friday Mono, behind the opt-in OpenType feature ss02 ("Coding ligatures").

Default shaping is unchanged: nothing here runs unless ss02 is on.

Technique (the one Paper Mono and Fira Code use, so every character keeps its 600-unit cell and
terminals/editors see no wide glyphs): for a sequence of n characters, the first n-1 characters are
replaced by an empty spacer glyph and the last one by a ligature glyph that has a negative left side
bearing and draws the whole shape across the n cells.

The shapes are built from Friday Mono's own `= - < > /` glyphs of the same style (bar thickness,
chevron angle and stroke weight follow the weight automatically).  Paper Mono (OFL) was used as the
reference for which sequences exist and how they look; none of its outlines or lookups are used.

    ligatures.add(font)          # draws the glyphs and adds the ss02 lookups to GSUB
"""
import math

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.misc.transform import Transform
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.removeOverlaps import removeOverlaps

ADVANCE = 600
SPACER = 'lig.spc'
FEATURE = 'ss02'
LABEL = 'Coding ligatures'

# --- the sequences ---------------------------------------------------------------
# kind: bars (== ===), chain (arrows and double chevrons: -> => <-> <=> >> >>= =>> ...),
#       neq (!= !== =/= /=), cmp (>= <=: a chevron over a bar)
SEQUENCES = [
    ('==', 'bars'), ('===', 'bars'),
    ('->', 'chain'), ('-->', 'chain'), ('=>', 'chain'), ('==>', 'chain'),
    ('<-', 'chain'), ('<--', 'chain'), ('<->', 'chain'), ('<-->', 'chain'), ('<=>', 'chain'), ('<==', 'chain'),
    ('>>', 'chain'), ('<<', 'chain'), ('>>=', 'chain'), ('<<=', 'chain'), ('=>>', 'chain'), ('=<<', 'chain'),
    ('!=', 'neq'), ('!==', 'neq'), ('=/=', 'neq'), ('/=', 'neq'),
    ('>=', 'cmp'), ('<=', 'cmp'),
    ('|>', 'tri'), ('<|', 'tri'), ('<|>', 'tri'),
]

CHARS = '=-<>!/|'
OVERLAP = 3                           # pieces overlap by this much (the italic's rounded coordinates are off by up to 1)
PAIR_SHIFT = 210                      # two chevrons in a row are drawn this much closer than a cell


# --- geometry in the unslanted frame ---------------------------------------------

def _contours(font, name, slant):
    """Contours of `name` as lists of (x, y), unslanted (italic undone).  Line segments only."""
    pen = DecomposingRecordingPen(font.getGlyphSet())
    font.getGlyphSet()[name].draw(pen)
    out = []
    for op, args in pen.value:
        if op == 'moveTo':
            out.append([args[0]])
        elif op == 'lineTo':
            out[-1].append(args[0])
        elif op in ('closePath', 'endPath'):
            pass
        else:
            raise SystemExit('%s has curves; ligatures.py draws only straight glyphs from it' % name)
    return [[(x - y * slant, y) for x, y in c] for c in out]


def _bbox(points):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _area(poly):
    return sum(poly[i - 1][0] * poly[i][1] - poly[i][0] * poly[i - 1][1] for i in range(len(poly))) / 2


def _inside(poly, x, y):
    """Ray casting; the polygon may be wound either way."""
    hit = False
    for i in range(len(poly)):
        (x0, y0), (x1, y1) = poly[i - 1], poly[i]
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            hit = not hit
    return hit


def chevron_polygon(xm, yc, half, phi, thick, flat):
    """A `>`-shaped chevron stroke: arms at angle phi to the axis, perpendicular stroke thickness
    `thick`, the tip cut square to a flat of height `flat`, arm ends cut square to the arm.
    xm = where the outer edges would meet (the sharp tip), yc = axis height, half = distance of the
    outer arm ends from the axis.  With the font's own numbers it reproduces the font's `>`."""
    tan, sin, cos = math.tan(phi), math.sin(phi), math.cos(phi)
    cut = flat / (2 * tan)
    gap = thick / cos
    e = half / tan
    return [(xm - e, yc - half), (xm - cut, yc - cut * tan), (xm - cut, yc + cut * tan), (xm - e, yc + half),
            (xm - e - thick * sin, yc + half - thick * cos), (xm - gap / tan, yc),
            (xm - e - thick * sin, yc - half + thick * cos)]


class Style:
    """Measurements of one style, all unslanted."""

    def __init__(self, font, slant):
        cmap = font.getBestCmap()
        self.font, self.slant = font, slant
        self.name = {c: cmap[ord(c)] for c in CHARS}
        hy = _contours(font, self.name['-'], slant)
        eq = _contours(font, self.name['='], slant)
        self.hy_x0, self.hy_y0, self.hy_x1, self.hy_y1 = _bbox(hy[0])
        bars = sorted((_bbox(c) for c in eq), key=lambda b: b[1])
        self.eq_bars = [(b[1], b[3]) for b in bars]                 # (y0, y1), bottom first
        self.eq_x0 = min(b[0] for b in bars)
        self.eq_x1 = max(b[2] for b in bars)
        # orientation of the font's own rectangles: new rectangles must wind the same way
        self.sign = 1 if _area(hy[0]) > 0 else -1
        self.poly = {'>': max(_contours(font, self.name['>'], slant), key=len),
                     '<': max(_contours(font, self.name['<'], slant), key=len)}
        # the font's own chevron in numbers: arm angle, stroke thickness, tip flat
        gt = self.poly['>']
        x0, y0, x1, y1 = _bbox(gt)
        yc = (y0 + y1) / 2
        flat = [p for p in gt if p[0] > x1 - 3]
        self.chev_flat = max(p[1] for p in flat) - min(p[1] for p in flat)
        low_end, low_tip = min(gt, key=lambda p: p[1]), min(flat, key=lambda p: p[1])
        self.chev_phi = math.atan2(low_tip[1] - low_end[1], low_tip[0] - low_end[0])
        inner = min((p for p in gt if p[0] < x1 - 10), key=lambda p: abs(p[1] - yc))
        xm = x1 + (self.chev_flat / 2) / math.tan(self.chev_phi)
        vertical = (xm - inner[0]) * math.tan(self.chev_phi)       # vertical stroke thickness
        self.chev_thick = vertical * math.cos(self.chev_phi)
        sl = _contours(font, self.name['/'], slant)[0]
        sx0, sy0, sx1, sy1 = _bbox(sl)
        # slash: a parallelogram.  slope = dx/dy of its edges, width = horizontal thickness.
        low = [p for p in sl if p[1] < sy0 + 1]
        high = [p for p in sl if p[1] > sy1 - 1]
        lx = sum(p[0] for p in low) / len(low)
        hx = sum(p[0] for p in high) / len(high)
        self.slash_slope = (hx - lx) / (sy1 - sy0)
        self.slash_width = max(p[0] for p in low) - min(p[0] for p in low)

    def bar_ranges(self, ch):
        return [(self.hy_y0, self.hy_y1)] if ch == '-' else list(self.eq_bars)

    def bar_x(self, ch):
        return (self.hy_x0, self.hy_x1) if ch == '-' else (self.eq_x0, self.eq_x1)

    def tip_inside(self, ch, ya, yb):
        """x (cell-local, unslanted) just inside the tip of chevron `ch`, where a bar [ya, yb] can be
        embedded without poking out of the strokes: bars are joined to the tip side."""
        poly = self.poly[ch]
        x0, _, x1, _ = _bbox(poly)
        ys = [ya + (yb - ya) * k / 8 for k in range(9)]
        direction = 1 if ch == '>' else -1
        xs = [x1 - k for k in range(int(x1 - x0))] if direction > 0 else [x0 + k for k in range(int(x1 - x0))]
        for x in xs:
            if all(_inside(poly, x - direction * 1.5, y) for y in ys):
                return x - direction * 2
        raise SystemExit('bar does not reach into the chevron')


class Drawer:
    """Collects components and polygons for one ligature glyph (unslant -> move -> reslant)."""

    def __init__(self, style, n):
        self.st, self.n = style, n
        self.pen = TTGlyphPen(None)
        self.slant = style.slant

    def dx(self, cell):
        return -(self.n - 1 - cell) * ADVANCE

    def component(self, ch, cell, dx_extra=0):
        s = self.slant
        move = Transform(1, 0, 0, 1, self.dx(cell) + dx_extra, 0)
        total = Transform(1, 0, s, 1, 0, 0).transform(move).transform(Transform(1, 0, -s, 1, 0, 0))
        self.st.font.getGlyphSet()[self.st.name[ch]].draw(TransformPen(self.pen, total))

    def polygon(self, pts, hole=False):
        """A polygon in the unslanted frame, wound like the font's own rectangles (a hole: the other way)."""
        s = self.slant
        if (_area(pts) > 0) != ((self.st.sign > 0) != hole):
            pts = pts[::-1]
        pts = [(round(x + y * s), round(y)) for x, y in pts]
        self.pen.moveTo(pts[0])
        for p in pts[1:]:
            self.pen.lineTo(p)
        self.pen.closePath()

    def rect(self, x0, y0, x1, y1):
        if x1 > x0:
            self.polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])

    def parallelogram(self, cx, y0, y1):
        k, w = self.st.slash_slope, self.st.slash_width
        mid = (y0 + y1) / 2

        def x_at(y):
            return cx + (y - mid) * k
        self.polygon([(x_at(y0) - w / 2, y0), (x_at(y0) + w / 2, y0), (x_at(y1) + w / 2, y1), (x_at(y1) - w / 2, y1)])

    def glyph(self):
        return self.pen.glyph()


def _fill_bars(d, ch, left_cell, right_cell):
    """Connect the bar glyph of `ch` in left_cell to the one in right_cell (adjacent cells)."""
    x0, x1 = d.st.bar_x(ch)
    for ya, yb in d.st.bar_ranges(ch):
        d.rect(x1 + d.dx(left_cell) - OVERLAP, ya, x0 + d.dx(right_cell) + OVERLAP, yb)


def _chain(d, seq):
    """Bars (`-` `=`) and chevrons in a row.  Chevrons in a run of two are drawn closer together.
    A bar next to a chevron runs into its tip (the shaft of an arrow, the bar of >>=)."""
    st, n = d.st, len(seq)
    shift = [0] * n
    for i in range(n - 1):
        if seq[i] == seq[i + 1] and seq[i] in '<>':
            if seq[i] == '>':
                shift[i] = PAIR_SHIFT
            else:
                shift[i + 1] = -PAIR_SHIFT
    for i, c in enumerate(seq):
        d.component(c, i, shift[i])
    for i in range(n - 1):
        a, b = seq[i], seq[i + 1]
        if a in '-=' and b in '-=':
            _fill_bars(d, a, i, i + 1)
        elif a in '-=' and b in '<>':
            # a bar meets only the nearest chevron: it runs through the notch of a `>` to its tip (an
            # arrow's shaft) and stops at the tip of a `<`
            x0, x1 = st.bar_x(a)
            for ya, yb in st.bar_ranges(a):
                d.rect(x1 + d.dx(i) - OVERLAP, ya, st.tip_inside(b, ya, yb) + d.dx(i + 1) + shift[i + 1], yb)
        elif a in '<>' and b in '-=':
            x0, x1 = st.bar_x(b)
            for ya, yb in st.bar_ranges(b):
                d.rect(st.tip_inside(a, ya, yb) + d.dx(i) + shift[i], ya, x0 + d.dx(i + 1) + OVERLAP, yb)


def _cmp(d, seq):
    """>= and <=: a flatter chevron over a bar, centred on the two cells."""
    st = d.st
    phi = math.radians(20)
    half, yc = 235, 420
    pts = chevron_polygon(0, yc, half, phi, st.chev_thick, st.chev_flat * 0.9)
    x0, _, x1, _ = _bbox(pts)
    left = d.dx(0) + (2 * ADVANCE - (x1 - x0)) / 2
    pts = [(x - x0 + left, y) for x, y in pts] if seq[0] == '>' else [(x1 - x + left, y) for x, y in pts]
    d.polygon(pts)
    bx0, _, bx1, _ = _bbox(pts)
    d.rect(bx0, 70, bx1, 70 + st.hy_y1 - st.hy_y0)


def _triangle(tip_x, base_x, y0, y1, thick):
    """(outer, inner) of an outlined triangle: tip at tip_x, vertical base at base_x spanning y0..y1,
    stroke `thick`.  The inner one is the outer scaled about its incentre by (r - thick) / r."""
    yc = (y0 + y1) / 2
    outer = [(base_x, y0), (tip_x, yc), (base_x, y1)]
    a, b, c = (math.hypot(outer[1][0] - outer[2][0], outer[1][1] - outer[2][1]),
               math.hypot(outer[0][0] - outer[2][0], outer[0][1] - outer[2][1]),
               math.hypot(outer[0][0] - outer[1][0], outer[0][1] - outer[1][1]))
    per = a + b + c
    ix = (a * outer[0][0] + b * outer[1][0] + c * outer[2][0]) / per
    iy = (a * outer[0][1] + b * outer[1][1] + c * outer[2][1]) / per
    r = abs(_area(outer)) * 2 / per
    k = (r - thick) / r
    return outer, [(ix + (x - ix) * k, iy + (y - iy) * k) for x, y in outer]


def _tri(d, seq):
    """|> <| <|>: outlined triangles; <|> is a diamond with a bar through the middle."""
    st = d.st
    thick = (st.hy_y1 - st.hy_y0) * 0.95
    y0, y1 = 10, 690
    wide = 760                                                     # base to tip
    if seq == '<|>':
        mid = d.dx(0) + ADVANCE * 1.5                              # centre of the three cells
        half = thick / 2
        lo, li = _triangle(mid - wide + half, mid + half, y0, y1, thick)   # tip left, base at the centre bar
        ro, ri = _triangle(mid + wide - half, mid - half, y0, y1, thick)
        yc = (y0 + y1) / 2
        apex = (y1 - yc) * (wide - half) / wide                    # where the two outer edges meet at x = mid
        d.polygon([lo[1], (mid, yc + apex), ro[1], (mid, yc - apex)])
        d.polygon(li, hole=True)
        d.polygon(ri, hole=True)
        return
    mid = d.dx(0) + ADVANCE                                        # centre of the two cells
    tip, base = (mid + wide / 2, mid - wide / 2) if seq == '|>' else (mid - wide / 2, mid + wide / 2)
    outer, inner = _triangle(tip, base, y0, y1, thick)
    d.polygon(outer)
    d.polygon(inner, hole=True)


def build(style, seq, kind):
    n = len(seq)
    d = Drawer(style, n)
    if kind == 'bars':
        for i in range(n):
            d.component(seq[i], i)
            if i:
                _fill_bars(d, seq[i], i - 1, i)
    elif kind == 'chain':
        _chain(d, seq)
    elif kind == 'neq':
        for i in range(n):
            d.component('=', i)
            if i:
                _fill_bars(d, '=', i - 1, i)
        lo, hi = style.eq_bars[0][0] - 95, style.eq_bars[-1][1] + 95
        d.parallelogram(d.dx(0) + ADVANCE * n / 2, lo, hi)
    elif kind == 'cmp':
        _cmp(d, seq)
    elif kind == 'tri':
        _tri(d, seq)
    else:
        raise ValueError(kind)
    return d.glyph()


# --- glyph names, GSUB ----------------------------------------------------------

def glyph_name(font, seq):
    cmap = font.getBestCmap()
    return '_'.join(cmap[ord(c)] for c in seq) + '.liga'


def _add_glyphs(font, glyphs):
    """glyphs: {name: TTGlyph}.  New glyphs have no code point: own adder (build's add_glyphs needs one)."""
    glyf, hmtx = font['glyf'], font['hmtx']
    order = list(font.getGlyphOrder())
    for name, glyph in glyphs.items():
        glyf[name] = glyph
        glyph.recalcBounds(glyf)
        hmtx[name] = (ADVANCE, getattr(glyph, 'xMin', 0))
    final = list(dict.fromkeys(order + list(glyphs)))
    font.setGlyphOrder(final)
    glyf.glyphOrder = final
    if 'GDEF' in font and font['GDEF'].table.GlyphClassDef:
        for name in glyphs:
            font['GDEF'].table.GlyphClassDef.classDefs[name] = 1


def feature_code(font):
    names = {c: font.getBestCmap()[ord(c)] for c in CHARS}
    out = ['lookup LIG_SPC { sub [%s] by %s; } LIG_SPC;' % (' '.join(names.values()), SPACER)]
    for seq, _ in SEQUENCES:
        lig = glyph_name(font, seq)
        out.append('lookup LIG_%s { sub %s by %s; } LIG_%s;' % (lig[:-5], names[seq[-1]], lig, lig[:-5]))
    body = []
    for seq, _ in sorted(SEQUENCES, key=lambda s: -len(s[0])):          # longest first
        first, last = names[seq[0]], names[seq[-1]]
        marked = ' '.join("%s'" % names[c] for c in seq)
        # never inside a longer run of the same first / last character (====, ->>, <<=)
        body.append('    ignore sub %s %s;' % (first, marked))
        body.append('    ignore sub %s %s;' % (marked, last))
        chain = ' '.join("%s' lookup LIG_SPC" % names[c] for c in seq[:-1])
        chain += " %s' lookup LIG_%s" % (last, glyph_name(font, seq)[:-5])
        body.append('    sub %s;' % chain)
    out.append('feature %s { lookup LIG_MAIN {\n%s\n  } LIG_MAIN; } %s;' % (FEATURE, '\n'.join(body), FEATURE))
    return '\n'.join(out)


def _langsys(script_list):
    for rec in script_list.ScriptRecord:
        if rec.Script.DefaultLangSys:
            yield rec.Script.DefaultLangSys
        for l in rec.Script.LangSysRecord:
            yield l.LangSys


def _nested_records(sub):
    """Every SubstLookupRecord of a contextual subtable, whatever its format (1, 2 or 3)."""
    if sub.LookupType == 7:
        sub = sub.ExtSubTable
    found = list(getattr(sub, 'SubstLookupRecord', None) or [])
    for sets, rules in (('ChainSubRuleSet', 'ChainSubRule'), ('ChainSubClassSet', 'ChainSubClassRule')):
        for rule_set in getattr(sub, sets, None) or []:
            for rule in (getattr(rule_set, rules, None) or []) if rule_set is not None else []:
                found += rule.SubstLookupRecord
    return found


def _merge_gsub(font, scratch):
    """Append the lookups of `scratch` (compiled in a throw-away font) to font's GSUB, keeping what is there."""
    src, dst = scratch['GSUB'].table, font['GSUB'].table
    base = len(dst.LookupList.Lookup)
    for lookup in src.LookupList.Lookup:
        for sub in lookup.SubTable:
            for rec in _nested_records(sub):
                rec.LookupListIndex += base
        dst.LookupList.Lookup.append(lookup)
    dst.LookupList.LookupCount = len(dst.LookupList.Lookup)
    feature = [r for r in src.FeatureList.FeatureRecord if r.FeatureTag == FEATURE][0]
    feature.Feature.LookupListIndex = [i + base for i in feature.Feature.LookupListIndex]
    records = dst.FeatureList.FeatureRecord
    records.append(feature)
    new_index = len(records) - 1
    for ls in _langsys(dst.ScriptList):
        ls.FeatureIndex.append(new_index)
    # FeatureRecords must stay sorted by tag; remap every index that points at them
    order = sorted(range(len(records)), key=lambda i: records[i].FeatureTag)
    remap = {old: new for new, old in enumerate(order)}
    dst.FeatureList.FeatureRecord = [records[i] for i in order]
    dst.FeatureList.FeatureCount = len(records)
    for ls in _langsys(dst.ScriptList):
        ls.FeatureIndex = sorted(remap[i] for i in ls.FeatureIndex)
        ls.FeatureCount = len(ls.FeatureIndex)
        if ls.ReqFeatureIndex != 0xFFFF:
            ls.ReqFeatureIndex = remap[ls.ReqFeatureIndex]


def add(font):
    """Add the ss02 ligatures to `font` (an unhinted Friday Mono style).  Returns the new glyph names."""
    slant = math.tan(math.radians(-font['post'].italicAngle))
    style = Style(font, slant)
    glyphs = {SPACER: TTGlyphPen(None).glyph()}
    for seq, kind in SEQUENCES:
        glyphs[glyph_name(font, seq)] = build(style, seq, kind)
    _add_glyphs(font, glyphs)
    drawn = [n for n in glyphs if n != SPACER]
    removeOverlaps(font, glyphNames=drawn, removeHinting=False)      # one clean outline per shape (the pieces overlap)
    for n in drawn:                                                  # keep lsb = xMin after the union
        font['glyf'][n].recalcBounds(font['glyf'])
        font['hmtx'][n] = (ADVANCE, font['glyf'][n].xMin)
    scratch = TTFont()
    scratch.setGlyphOrder(font.getGlyphOrder())
    scratch['maxp'] = newTable('maxp')
    scratch['maxp'].numGlyphs = len(font.getGlyphOrder())
    addOpenTypeFeaturesFromString(scratch, feature_code(font), tables=['GSUB'])
    _merge_gsub(font, scratch)
    return list(glyphs)
