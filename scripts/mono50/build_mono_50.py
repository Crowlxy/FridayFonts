"""Build Friday Mono 5.0 (Latin only) from the shipped 4.93 fonts.

    py scripts/mono50/build_mono_50.py

Input is the released FridayMono-4.93.zip; every TTF is checked against the
4.93 manifest before it is used.  The Japanese families (Friday Mono JP and
Friday Mono Plain JP) are discontinued in 5.0, so only the ten FridayMono-*
faces are rebuilt.  Output goes to work/mono-5.0/ (ignored by git).

What 5.0 changes, all measured against six other monospace fonts
(Cascadia Mono, Consolas, Geist Mono, Paper Mono, Fragment Mono, Roboto Mono):

1. Outlines: the faceted round extrema left by the 4.9x Latin build are
   repaired (outline_repair.py) and the faces are re-hinted from scratch with
   ttfautohint.  4.93 rendered C O G S o c e s 1-2 px taller than H x at
   9-32 px; the references and 5.0 render them the same height.
2. Line box: 880/-400 put the line centre 128 units below the cap-height
   centre (references: about 0).  968/-312 keeps the 1.28 em line and the
   Windows Terminal double underline (8-24 pt, 96-192 dpi) and moves the
   centre to -40.
3. Box drawing and block elements are fitted to the new line box, and their
   cell edges are snapped to 0/600 (Light stopped at 9/591 and left gaps).
4. Character set: coverage.json (coverage_votes.py) -- 68 characters fewer
   than two references carry are removed, 20 glyphs 4.93 drew but never
   mapped are mapped, 22 geometric and punctuation characters are derived
   from Friday's own outlines.
5. GDI metrics: usWin* came from the Japanese build (1.93 em line in GDI).
   They now cover the ink of every mapped glyph, so stacked Vietnamese and
   ring-acute capitals are not clipped in GDI (the cost is a taller GDI line).
6. Names and OS/2: version 5.002 (5.0.2), sample text without mojibake, Unicode and
   code page ranges recomputed, vertical tables from the CJK build dropped.
"""
import hashlib
import io
import json
import math
import shutil
import sys
import zipfile
from pathlib import Path

from fontTools.misc.transform import Transform
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import GlyphComponent, Glyph

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]                      # FridayFonts/
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from outline_repair import repair_glyph    # noqa: E402
import heights                            # noqa: E402
import inherited_fixes                    # noqa: E402

ZIP = ROOT / 'FridayMono-4.93.zip'
MANIFEST = ROOT / 'releases/mono-4.93/font-manifest.json'
COVERAGE = HERE / 'coverage.json'
OUT = ROOT / 'work/mono-5.0'

VERSION = '5.002'
REVISION = 5.002
STYLES = [('Light', 300), ('LightItalic', 300), ('Regular', 400), ('Italic', 400),
          ('Medium', 500), ('MediumItalic', 500), ('SemiBold', 600),
          ('SemiBoldItalic', 600), ('Bold', 700), ('BoldItalic', 700)]

ASCENT, DESCENT = 968, -312                 # 1.280 em, unchanged from 4.92
OLD_LINE = (-285, 965)                      # Iosevka's box-drawing line box
BOX = (0x2500, 0x259F)
NO_SNAP = {0x2571, 0x2572, 0x2573, 0x2591, 0x2592, 0x2593}
SNAP = 12
ADVANCE = 600
SYMBOL_AXIS = 340                           # centre of Iosevka's geometric shapes
WIN_MARGIN = 32
SAMPLE = 'Friday Mono 0123456789 Il1| O0 {} => != <= -> www'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_inputs():
    manifest = {row['ttf']: row for row in json.loads(MANIFEST.read_text(encoding='utf-8'))}
    fonts = {}
    with zipfile.ZipFile(ZIP) as archive:
        for style, _ in STYLES:
            rel = 'ttf/FridayMono-%s.ttf' % style
            data = archive.read('FridayMono-4.93/' + rel)
            expected = manifest[rel]['sha256']
            if sha(data) != expected:
                raise SystemExit('hash mismatch for %s' % rel)
            fonts[style] = (data, expected)
    return fonts


# --- character set ---------------------------------------------------------

def apply_coverage(font, coverage):
    cmap_tables = [t for t in font['cmap'].tables if t.isUnicode()]
    order = set(font.getGlyphOrder())
    for row in coverage['map_existing']:
        cp, glyph = int(row['cp'][2:], 16), row['glyph']
        if glyph not in order:
            raise SystemExit('missing glyph %s' % glyph)
        for table in cmap_tables:
            if table.format in (4, 12) and (table.format == 12 or cp <= 0xFFFF):
                table.cmap[cp] = glyph
    unicodes = set(coverage['keep']) | {int(r['cp'][2:], 16) for r in coverage['map_existing']}
    options = Options()
    options.layout_features = ['*']
    options.layout_scripts = ['*']
    options.name_IDs = ['*']
    options.name_languages = ['*']
    options.name_legacy = True
    options.glyph_names = True
    options.notdef_glyph = True
    options.notdef_outline = True
    options.recommended_glyphs = True
    options.hinting = False
    options.legacy_kern = True
    options.prune_unicode_ranges = False
    options.drop_tables = list(options.drop_tables) + ['vhea', 'vmtx', 'ltag']
    subsetter = Subsetter(options)
    subsetter.populate(unicodes=unicodes)
    subsetter.subset(font)
    missing = unicodes - set(font.getBestCmap())
    if missing:
        raise SystemExit('lost characters: %s' % sorted(missing))


# --- outlines ----------------------------------------------------------------

def repair_outlines(font):
    glyf = font['glyf']
    dropped = tents = 0
    for name in font.getGlyphOrder():
        d, t = repair_glyph(glyf[name], glyf)
        dropped += d
        tents += t
    return dropped, tents


def fix_inherited(font, style, inputs):
    """Outline defects of the 4.93 faces (inherited_fixes.py)."""
    rev = {}
    for cp, name in font.getBestCmap().items():
        rev.setdefault(name, cp)
    label = lambda n: 'U+%04X' % rev[n] if n in rev else n
    done = {}
    if style == 'Light' and inherited_fixes.splice_light_dje(font):
        done['U+0402'] = 'inner arc of the bowl spliced back'
    for name, actions in inherited_fixes.fix_reversed(font).items():
        done[label(name)] = ', '.join('reversed contour %d %s' % a for a in actions)
    reference = TTFont(io.BytesIO(inputs['Italic' if style.endswith('Italic') else 'Regular'][0]))
    if style == 'Light' and inherited_fixes.rebuild_light_half(font, reference):
        done['U+00BD'] = 'denominator redrawn from the Light digit 2'
    if inherited_fixes.rebuild_from_reference(font, reference, 0x212E):
        done['U+212E'] = 'loose pieces replaced by the %s outline' % ('Italic' if style.endswith('Italic') else 'Regular')
    return done


def fit_box_drawing(font):
    glyf, cmap = font['glyf'], font.getBestCmap()
    scale = (ASCENT - DESCENT) / (OLD_LINE[1] - OLD_LINE[0])
    done = 0
    for cp in range(BOX[0], BOX[1] + 1):
        name = cmap.get(cp)
        if not name:
            continue
        glyph = glyf[name]
        if glyph.numberOfContours <= 0:
            continue
        coords = glyph.coordinates
        for i in range(len(coords)):
            x, y = coords[i]
            if cp not in NO_SNAP:
                if abs(x) <= SNAP:
                    x = 0
                elif abs(x - ADVANCE) <= SNAP:
                    x = ADVANCE
                if abs(y - OLD_LINE[0]) <= SNAP:
                    y = OLD_LINE[0]
                elif abs(y - OLD_LINE[1]) <= SNAP:
                    y = OLD_LINE[1]
            coords[i] = (x, round(DESCENT + (y - OLD_LINE[0]) * scale))
        glyph.recalcBounds(glyf)
        font['hmtx'][name] = (font['hmtx'][name][0], glyph.xMin)
        done += 1
    return done


# --- derived glyphs ------------------------------------------------------------

def slant_of(font):
    return math.tan(math.radians(-font['post'].italicAngle))


def unslanted_points(font, name, slant):
    pen = DecomposingRecordingPen(font.getGlyphSet())
    font.getGlyphSet()[name].draw(pen)
    pts = []
    for op, args in pen.value:
        for point in args:
            if point is not None:
                pts.append((point[0] - point[1] * slant, point[1]))
    return pen.value, pts


def bbox(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def area(poly):
    return sum(poly[i - 1][0] * poly[i][1] - poly[i][0] * poly[i - 1][1]
               for i in range(len(poly))) / 2


def clockwise(poly):
    return poly if area(poly) < 0 else poly[::-1]


def inset(poly, d):
    """Inset a convex clockwise polygon by d (y up)."""
    poly = clockwise(poly)
    n = len(poly)
    lines = []
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        nx, ny = dy / length, -dx / length          # right normal = inside for clockwise (y up)
        lines.append(((x0 + nx * d, y0 + ny * d), (dx, dy)))
    out = []
    for i in range(n):
        (p, r), (q, s) = lines[i - 1], lines[i]
        cross = r[0] * s[1] - r[1] * s[0]
        t = ((q[0] - p[0]) * s[1] - (q[1] - p[1]) * s[0]) / cross
        out.append((p[0] + t * r[0], p[1] + t * r[1]))
    if not all(inside(pt, poly) for pt in out) or abs(area(out)) >= abs(area(poly)):
        raise SystemExit('inset left the outline: %s -> %s' % (poly, out))
    return out


def inside(point, poly):
    """Strictly inside a convex polygon (either orientation)."""
    x, y = point
    signs = []
    for i in range(len(poly)):
        (x0, y0), (x1, y1) = poly[i - 1], poly[i]
        signs.append((x1 - x0) * (y - y0) - (y1 - y0) * (x - x0))
    return all(v > 0 for v in signs) or all(v < 0 for v in signs)


def polygon_glyph(contours, slant):
    pen = TTGlyphPen(None)
    for i, poly in enumerate(contours):
        poly = clockwise(poly) if i == 0 else clockwise(poly)[::-1]
        pts = [(round(x + y * slant), round(y)) for x, y in poly]
        pen.moveTo(pts[0])
        for p in pts[1:]:
            pen.lineTo(p)
        pen.closePath()
    return pen.glyph()


def transformed_glyph(font, name, slant, matrix, reverse=False):
    """Draw `name` through unslant -> matrix -> reslant."""
    unslant = Transform(1, 0, -slant, 1, 0, 0)
    reslant = Transform(1, 0, slant, 1, 0, 0)
    total = reslant.transform(matrix).transform(unslant)
    pen = TTGlyphPen(None)
    target = ReverseContourPen(pen) if reverse else pen
    font.getGlyphSet()[name].draw(TransformPen(target, total))
    return pen.glyph()


def triangle(cx, cy, w, h, direction):
    """Filled triangle with its point in `direction`, base w and height h."""
    if direction == 'up':
        return [(cx, cy + h / 2), (cx + w / 2, cy - h / 2), (cx - w / 2, cy - h / 2)]
    if direction == 'down':
        return [(cx, cy - h / 2), (cx - w / 2, cy + h / 2), (cx + w / 2, cy + h / 2)]
    if direction == 'right':
        return [(cx + h / 2, cy), (cx - h / 2, cy - w / 2), (cx - h / 2, cy + w / 2)]
    return [(cx - h / 2, cy), (cx + h / 2, cy + w / 2), (cx + h / 2, cy - w / 2)]


def derive_symbols(font, wanted):
    cmap = font.getBestCmap()
    slant = slant_of(font)
    _, tri_pts = unslanted_points(font, cmap[0x25B2], slant)
    tx0, ty0, tx1, ty1 = bbox(tri_pts)
    cx, cy = (tx0 + tx1) / 2, SYMBOL_AXIS
    w, h = tx1 - tx0, ty1 - ty0
    _, sq_pts = unslanted_points(font, cmap[0x25A1], slant)
    sq = font['glyf'][cmap[0x25A1]]
    coords, ends, _ = sq.getCoordinates(font['glyf'])
    outer = bbox([(x - y * slant, y) for x, y in coords[:ends[0] + 1]])
    inner = bbox([(x - y * slant, y) for x, y in coords[ends[0] + 1:]])
    stroke = min(abs(inner[1] - outer[1]), abs(outer[3] - inner[3]))
    sqx0, sqy0, sqx1, sqy1 = outer
    small = 0.6
    shapes = {
        0x25B2: [triangle(cx, cy, w, h, 'up')],
        0x25BC: [triangle(cx, cy, w, h, 'down')],
        0x25B6: [triangle(cx, cy, w, h, 'right')],
        0x25C0: [triangle(cx, cy, w, h, 'left')],
        0x25B4: [triangle(cx, cy, w * small, h * small, 'up')],
        0x25BE: [triangle(cx, cy, w * small, h * small, 'down')],
        0x25B8: [triangle(cx, cy, w * small, h * small, 'right')],
        0x25C2: [triangle(cx, cy, w * small, h * small, 'left')],
        0x25BA: [triangle(cx, cy, w * 0.6, h, 'right')],
        0x25C4: [triangle(cx, cy, w * 0.6, h, 'left')],
    }
    hollow = {0x25B3: (0x25B2, stroke), 0x25BD: (0x25BC, stroke),
              0x25B7: (0x25B6, stroke), 0x25C1: (0x25C0, stroke),
              0x25B5: (0x25B4, stroke * 0.85), 0x25BF: (0x25BE, stroke * 0.85),
              0x25B9: (0x25B8, stroke * 0.85), 0x25C3: (0x25C2, stroke * 0.85)}
    for cp, (base, d) in hollow.items():
        outer_poly = shapes[base][0]
        shapes[cp] = [outer_poly, inset(outer_poly, d)]
    half = min(sqx1 - sqx0, sqy1 - sqy0) * 1.1 / 2
    diamond = [(cx, cy + half), (cx + half, cy), (cx, cy - half), (cx - half, cy)]
    shapes[0x25C6] = [diamond]
    shapes[0x25C7] = [diamond, inset(diamond, stroke)]

    made = {}
    for cp, contours in shapes.items():
        if cp in (0x25B2, 0x25BC) or cp in wanted:
            made[cp] = polygon_glyph(contours, slant)

    if 0x25E6 in wanted:                     # white bullet: ring from the bullet
        bullet = cmap[0x2022]
        _, pts = unslanted_points(font, bullet, slant)
        bx0, by0, bx1, by1 = bbox(pts)
        bcx, bcy, dia = (bx0 + bx1) / 2, (by0 + by1) / 2, bx1 - bx0
        k = 1 - 2 * stroke * 0.85 / dia
        ring = TTGlyphPen(None)
        unslant = Transform(1, 0, -slant, 1, 0, 0)
        reslant = Transform(1, 0, slant, 1, 0, 0)
        font.getGlyphSet()[bullet].draw(ring)
        inner_m = Transform().translate(bcx, bcy).scale(k).translate(-bcx, -bcy)
        font.getGlyphSet()[bullet].draw(
            TransformPen(ReverseContourPen(ring), reslant.transform(inner_m).transform(unslant)))
        made[0x25E6] = ring.glyph()
    if 0x201B in wanted:                     # reversed comma quotation mark
        _, pts = unslanted_points(font, cmap[0x2019], slant)
        qx0, _, qx1, _ = bbox(pts)
        mirror = Transform(-1, 0, 0, 1, qx0 + qx1, 0)
        made[0x201B] = transformed_glyph(font, cmap[0x2019], slant, mirror, reverse=True)
    if 0x2017 in wanted:                     # double low line
        _, pts = unslanted_points(font, cmap[0x5F], slant)
        ux0, uy0, ux1, uy1 = bbox(pts)
        t = (uy1 - uy0) * 0.62
        gap = t * 0.8
        lower = [(ux0, uy0), (ux0, uy0 + t), (ux1, uy0 + t), (ux1, uy0)]
        upper = [(ux0, uy0 + t + gap), (ux0, uy0 + 2 * t + gap),
                 (ux1, uy0 + 2 * t + gap), (ux1, uy0 + t + gap)]
        pen = TTGlyphPen(None)
        for poly in (lower, upper):
            poly = clockwise(poly)
            pts2 = [(round(x + y * slant), round(y)) for x, y in poly]
            pen.moveTo(pts2[0])
            for p in pts2[1:]:
                pen.lineTo(p)
            pen.closePath()
        made[0x2017] = pen.glyph()
    if 0x203C in wanted:                     # double exclamation mark
        glyph = Glyph()
        glyph.numberOfContours = -1
        glyph.components = []
        for dx in (-135, 135):
            comp = GlyphComponent()
            comp.glyphName = cmap[0x21]
            comp.x, comp.y = dx, 0
            comp.flags = 0x4                           # ROUND_XY_TO_GRID
            glyph.components.append(comp)
        made[0x203C] = glyph
    return made


def add_glyphs(font, made):
    glyf, hmtx, cmap = font['glyf'], font['hmtx'], font.getBestCmap()
    order = list(font.getGlyphOrder())
    new_names = []
    for cp, glyph in sorted(made.items()):
        name = cmap.get(cp) or ('uni%04X' % cp)
        if name not in glyf:
            new_names.append(name)
        glyf[name] = glyph
        glyph.recalcBounds(glyf)
        hmtx[name] = (ADVANCE, getattr(glyph, 'xMin', 0))
        for table in font['cmap'].tables:
            if table.isUnicode() and table.format in (4, 12):
                table.cmap[cp] = name
    final = list(dict.fromkeys(order + new_names))
    font.setGlyphOrder(final)
    glyf.glyphOrder = final
    if 'GDEF' in font and font['GDEF'].table.GlyphClassDef:
        classes = font['GDEF'].table.GlyphClassDef.classDefs
        for name in new_names:
            classes[name] = 1
    return new_names


# --- metrics and names ---------------------------------------------------------

def family_win(fonts):
    """Ink extent of every glyph (mapped or not), composites included, from the drawn outlines."""
    top = bottom = 0
    for font in fonts.values():
        glyphs = font.getGlyphSet()
        for name in font.getGlyphOrder():
            pen = BoundsPen(glyphs)
            glyphs[name].draw(pen)
            if pen.bounds is None:
                continue
            top = max(top, math.ceil(pen.bounds[3]))
            bottom = max(bottom, math.ceil(-pen.bounds[1]))
    # ttfautohint's Windows-compatibility mode puts a blue zone on usWinAscent;
    # within ~27 units of the line top it pulls the top edge of the box
    # verticals (968) and collapses them at 9-23 px.  Keep a clear margin.
    return max(top, ASCENT + WIN_MARGIN), max(bottom, -DESCENT)


def set_metrics(font, win):
    hhea, os2 = font['hhea'], font['OS/2']
    hhea.ascent, hhea.descent, hhea.lineGap = ASCENT, DESCENT, 0
    os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = ASCENT, DESCENT, 0
    os2.usWinAscent, os2.usWinDescent = win
    os2.fsSelection |= 1 << 7                       # USE_TYPO_METRICS
    os2.recalcUnicodeRanges(font)
    os2.recalcCodePageRanges(font)
    os2.recalcAvgCharWidth(font)
    font['head'].fontRevision = REVISION


def set_names(font, style):
    name = font['name']
    ps = 'FridayMono-' + style
    values = {
        3: 'FridayProject;%s;%s' % (VERSION, ps),
        5: 'Version %s' % VERSION,
        10: ('Friday Mono 5.0.2: Latin-only coding font. Round letters re-hinted to '
             'the cap and x-height, line box centred on the text, box drawing '
             'fitted to the line, character set compared with six monospace fonts.'),
        19: SAMPLE,
    }
    mac = any(rec.platformID == 1 for rec in name.names)
    for nid, text in values.items():
        name.removeNames(nameID=nid)
        name.setName(text, nid, 3, 1, 0x409)
        if mac:
            name.setName(text, nid, 1, 0, 0)


def main():
    coverage = json.loads(COVERAGE.read_text(encoding='utf-8'))
    wanted = {int(r['cp'][2:], 16) for r in coverage['add']}
    inputs = load_inputs()
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / 'unhinted').mkdir(parents=True)
    fonts, log = {}, {}
    for style, _ in STYLES:
        data, digest = inputs[style]
        font = TTFont(io.BytesIO(data))
        apply_coverage(font, coverage)
        inherited = fix_inherited(font, style, inputs)
        dropped, tents = repair_outlines(font)
        boxes = fit_box_drawing(font)
        made = derive_symbols(font, wanted)
        new = add_glyphs(font, made)
        targets = heights.style_targets(font)
        plans = heights.classify(font, targets)
        heights.apply(font, plans, targets)
        for name in plans:                    # scaling can level new facets
            repair_glyph(font['glyf'][name], font['glyf'])
        anchors = heights.move_anchors(font, plans)
        font['OS/2'].sCapHeight = round(targets['new_cap'])
        fonts[style] = font
        log[style] = {'input_sha256': digest, 'inherited_fixes': inherited, 'points_dropped': dropped,
                      'tents_repaired': tents, 'box_glyphs_fitted': boxes,
                      'glyphs_added': new, 'redrawn': ['U+25B2', 'U+25BC'],
                      'heights': {k: round(v, 3) for k, v in targets.items()},
                      'height_classes': heights.summary(plans),
                      'height_plans': {n: p.kind for n, p in plans.items()},
                      'digit_ends': {n: {'top': 'flat' if p.flat[0] else 'round', 'bottom': 'flat' if p.flat[1] else 'round'}
                                     for n, p in plans.items() if hasattr(p, 'flat')},
                      'anchors_moved': anchors}
        print('%-15s dropped %5d points, repaired %3d tents, fitted %3d box glyphs, added %d, '
              'heights %s (cap %.1f, asc %.1f, stroke %d), anchors %d'
              % (style, dropped, tents, boxes, len(new), heights.summary(plans),
                 targets['new_cap'], targets['new_ascender'], targets['stroke'], anchors), flush=True)
    win = family_win(fonts)
    print('usWinAscent/Descent', win)
    for style, _ in STYLES:
        font = fonts[style]
        set_metrics(font, win)
        set_names(font, style)
        font.save(OUT / 'unhinted' / ('FridayMono-%s.ttf' % style))

    import rehint                                     # scripts/rehint.py
    hinted = OUT / 'ttf'
    shutil.copytree(OUT / 'unhinted', hinted)
    sys.argv = ['rehint.py', '--dir', str(hinted)]
    status = rehint.main()
    for path in sorted(hinted.glob('*.ttf')):
        font = TTFont(path)
        font['gasp'].gaspRange = {0xFFFF: 0x000F}
        font.save(path)
    web = OUT / 'web'
    web.mkdir()
    css = []
    for style, weight in STYLES:
        font = TTFont(hinted / ('FridayMono-%s.ttf' % style))
        font.flavor = 'woff2'
        font.save(web / ('FridayMono-%s.woff2' % style))
        css.append('@font-face{font-family:"Friday Mono";src:url("FridayMono-%s.woff2") '
                   'format("woff2");font-weight:%d;font-style:%s;font-display:swap;}'
                   % (style, weight, 'italic' if 'Italic' in style else 'normal'))
    (web / 'friday-mono.css').write_text('\n'.join(css) + '\n', encoding='utf-8')
    (OUT / 'build-log.json').write_text(json.dumps(
        {'version': VERSION, 'ascent': ASCENT, 'descent': DESCENT, 'win': win,
         'rehint_status': status, 'styles': log}, indent=1), encoding='utf-8')
    return status


if __name__ == '__main__':
    sys.exit(main())
