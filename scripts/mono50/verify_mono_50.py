"""Verify Friday Mono 5.0 against the 4.93 input and the reference fonts.

    py scripts/mono50/verify_mono_50.py

Writes work/mono-5.0/reports/validation.json and fails (exit 1) on any
broken check.  Rendering is FreeType through Pillow (hinted, the TrueType
bytecode the font ships), plus outline-level checks with fontTools.
"""
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import uharfbuzz as hb
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from build_mono_50 import (ASCENT, DESCENT, BOX, MANIFEST, STYLES, ZIP,  # noqa: E402
                           OUT, COVERAGE)
from build_underline_trial import layout                                   # noqa: E402
from outline_repair import count_tents                                     # noqa: E402
import inherited_fixes                                                     # noqa: E402
import rehint                                                              # noqa: E402

REPORTS = OUT / 'reports'
SIZES = range(9, 33)
REDRAWN = {0x25B2, 0x25BC}
FAIL = []


def check(ok, message):
    if not ok:
        FAIL.append(message)
    return ok


def ink(face, text, px):
    img = Image.new('L', (px * 8, px * 4), 0)
    ImageDraw.Draw(img).text((px, px * 3), text, font=face, fill=255, anchor='ls')
    return img.getbbox()


def heights(path):
    """Pixel height difference of round letters against flat ones, 9-32 px."""
    rows = {}
    for px in SIZES:
        face = ImageFont.truetype(str(path), px)
        H, x = ink(face, 'H', px), ink(face, 'x', px)
        caps = {c: (ink(face, c, px)[1] - H[1], ink(face, c, px)[3] - H[3]) for c in 'COGSQ'}
        lower = {c: (ink(face, c, px)[1] - x[1], ink(face, c, px)[3] - x[3]) for c in 'oces'}
        rows[px] = {'caps': {c: v for c, v in caps.items() if v[0] or (c != 'Q' and v[1])},
                    'lower': {c: v for c, v in lower.items() if v != (0, 0)}}
    return rows


def render_all(path, cmap, glyf):
    errors, empty = [], []
    for px in (9, 11, 12, 13, 14, 16, 20, 24):
        face = ImageFont.truetype(str(path), px)
        for cp, name in cmap.items():
            glyph = glyf[name]
            if glyph.numberOfContours == 0:
                continue
            try:
                box = ink(face, chr(cp), px)
            except Exception as exc:                 # noqa: BLE001
                errors.append((px, cp, str(exc)))
                continue
            if box is None and px >= 12:
                empty.append((px, 'U+%04X' % cp))
    return errors, empty


def box_joins(path):
    """Gaps in ─ ═ █ rows and │ ║ █ columns when cells are packed edge to edge,
    and box verticals that do not fill their cell (8-50 px)."""
    gaps = []
    for px in range(8, 51):
        face = ImageFont.truetype(str(path), px)
        cell = round((ASCENT - DESCENT) * px / 1000)
        for ch in '│║█':
            box = ink(face, ch, px)
            if not box or box[3] - box[1] < cell - 1:
                gaps.append((px, ch, 'short %s' % (None if not box else box[3] - box[1])))
    for px in range(9, 25):
        face = ImageFont.truetype(str(path), px)
        cell = round((ASCENT - DESCENT) * px / 1000)
        base = round(ASCENT * px / 1000)
        for ch in '─═█':
            img = Image.new('L', (px * 12, cell + 4), 0)
            d = ImageDraw.Draw(img)
            for i in range(8):
                d.text((px + i * 0.6 * px, base), ch, font=face, fill=255, anchor='ls')
            cols = [img.crop((c, 0, c + 1, cell + 4)).getbbox() for c in range(img.width)]
            inked = [i for i, c in enumerate(cols) if c]
            if inked and len(inked) != inked[-1] - inked[0] + 1:
                gaps.append((px, ch, 'horizontal'))
        for ch in '│║█':
            img = Image.new('L', (px * 2, cell * 6 + 4), 0)
            d = ImageDraw.Draw(img)
            for i in range(5):
                d.text((px // 2, i * cell + base), ch, font=face, fill=255, anchor='ls')
            rows = [img.crop((0, r, img.width, r + 1)).getbbox() for r in range(img.height)]
            inked = [i for i, r in enumerate(rows) if r]
            if inked and len(inked) != inked[-1] - inked[0] + 1:
                gaps.append((px, ch, 'vertical'))
    return gaps


STROKES = [('H', 300), ('E', 300), ('T', 150), ('l', 200), ('seven', 300),
           ('bracketleft', 330), ('f', 470), ('O', 300), ('quotedbl', 230)]


def stroke_check(old, new):
    """Thickness of horizontal strokes (vertical ink runs), 4.93 vs 5.0."""
    sys.path.insert(0, str(HERE.parent / 'tools'))
    from scanline import flatten, spans_v
    from fontTools.pens.recordingPen import RecordingPen
    slant = __import__('math').tan(__import__('math').radians(-new['post'].italicAngle))
    out = {}
    for name, x in STROKES:
        runs = []
        for font in (old, new):
            if name not in font.getGlyphOrder():
                break
            pen = RecordingPen()
            font.getGlyphSet()[name].draw(pen)
            # upright the italic so a vertical scan crosses the strokes squarely
            pts = [[(px - py * slant, py) for px, py in poly] for poly in flatten(pen.value)]
            runs.append(sorted(round(b - a) for a, b in spans_v(pts, x)))
        if len(runs) == 2 and len(runs[0]) == len(runs[1]):
            for k, (a, b) in enumerate(zip(runs[0], runs[1])):
                out['%s#%d' % (name, k)] = (a, b)
    return out


def strokes_kept(strokes, stroke):
    """Horizontal strokes (runs no longer than 1.5 stems) within 2 units or 5 %."""
    bad = {}
    for key, (a, b) in strokes.items():
        if a <= 1.5 * stroke and abs(a - b) > max(2, 0.05 * a):
            bad[key] = (a, b)
    return bad


def shaping(path, cmap):
    blob = hb.Blob.from_file_path(str(path))
    face = hb.Face(blob)
    font = hb.Font(face)
    names = TTFont(path, lazy=True).getGlyphOrder()

    def shape(text, features=None):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(font, buf, features or {})
        return [names[i.codepoint] for i in buf.glyph_infos], [p.x_advance for p in buf.glyph_positions]

    import unicodedata as ud
    composed = bad = 0
    for cp in cmap:
        nfd = ud.normalize('NFD', chr(cp))
        if len(nfd) < 2 or not all(ord(c) in cmap for c in nfd):
            continue
        glyphs, advances = shape(nfd)
        composed += 1
        if sum(advances) != 600 or '.notdef' in glyphs:
            bad += 1
    zero = shape('0')[0][0]
    alt = shape('0', {'ss01': True})[0][0]
    cv = shape('0', {'cv01': True})[0][0]
    return {'decomposed_sequences': composed, 'decomposed_not_one_cell': bad,
            'zero': zero, 'zero_ss01': alt, 'zero_cv01': cv}


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    coverage = json.loads(COVERAGE.read_text(encoding='utf-8'))
    expected = set(coverage['keep']) | {int(r['cp'][2:], 16) for r in coverage['map_existing']} \
        | {int(r['cp'][2:], 16) for r in coverage['add']}
    added = {int(r['cp'][2:], 16) for r in coverage['add']}
    manifest = {row['ttf']: row for row in json.loads(MANIFEST.read_text(encoding='utf-8'))}
    archive = zipfile.ZipFile(ZIP)
    report = {'styles': {}}
    for style, weight in STYLES:
        path = OUT / 'ttf' / ('FridayMono-%s.ttf' % style)
        new = TTFont(path)
        old_bytes = archive.read('FridayMono-4.93/ttf/FridayMono-%s.ttf' % style)
        old = TTFont(io.BytesIO(old_bytes))
        check(hashlib.sha256(old_bytes).hexdigest() == manifest['ttf/FridayMono-%s.ttf' % style]['sha256'],
              '%s input hash' % style)
        cmap, ocmap = new.getBestCmap(), old.getBestCmap()
        glyf, oglyf = new['glyf'], old['glyf']
        r = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
             'characters': len(cmap), 'glyphs': len(new.getGlyphOrder())}
        check(set(cmap) == expected, '%s character set' % style)

        # outlines: same box and advance for every kept glyph whose height
        # was not changed on purpose (box drawing, redrawn, SF Mono heights,
        # 4.93 defects repaired)
        log = json.loads((OUT / 'build-log.json').read_text())['styles'][style]
        planned = set(log['height_plans'])
        repaired = {int(k[2:], 16) for k in log['inherited_fixes'] if k.startswith('U+')}
        moved, adv = [], []
        for cp, name in cmap.items():
            if cp not in ocmap or BOX[0] <= cp <= BOX[1] or cp in REDRAWN:
                continue
            if name in planned or cp in repaired:
                if new['hmtx'][name][0] != old['hmtx'][ocmap[cp]][0]:
                    adv.append('U+%04X' % cp)
                continue
            g, og = glyf[name], oglyf[ocmap[cp]]
            if new['hmtx'][name][0] != old['hmtx'][ocmap[cp]][0]:
                adv.append('U+%04X' % cp)
            if g.numberOfContours and og.numberOfContours:
                g.recalcBounds(glyf)
                og.recalcBounds(oglyf)
                if (g.xMin, g.yMin, g.xMax, g.yMax) != (og.xMin, og.yMin, og.xMax, og.yMax):
                    moved.append('U+%04X' % cp)
        r['outline_bbox_changed'] = moved
        r['advance_changed'] = adv
        check(not moved and not adv, '%s outlines/advances moved: %s %s' % (style, moved[:5], adv[:5]))
        # SF Mono proportions: targets reached, x-height kept, strokes kept
        h = log['heights']
        def top(ch):
            g = glyf[cmap[ord(ch)]]
            g.recalcBounds(glyf)
            return g.yMax
        r['heights'] = {'x': top('x'), 'H': top('H'), 'l': top('l'), 'barred_l': top('ł'),
                        'l_caron': top('ľ'), 'd': top('d'), 'zero': top('0'), 'one': top('1'),
                        'target_cap': h['new_cap'], 'target_ascender': h['new_ascender']}
        hr = r['heights']
        check(hr['x'] == h['x_height'], '%s x-height moved' % style)
        check(abs(hr['H'] - h['new_cap']) <= 1, '%s cap %s' % (style, hr['H']))
        check(abs(hr['l'] - h['new_ascender']) <= 1 and abs(hr['d'] - hr['l']) <= 1,
              '%s ascender %s' % (style, hr['l']))
        check(abs(hr['barred_l'] - hr['l']) <= 1, '%s l-stroke height %s vs l %s' % (style, hr['barred_l'], hr['l']))
        # digits: flat ends on H, round ends on O (heights._digit_plan)
        def ends(ch):
            g = glyf[cmap[ord(ch)]]
            g.recalcBounds(glyf)
            return g.yMax, g.yMin
        flat_ref, round_ref = ends('H'), ends('O')
        digit_rows = {}
        for ch in '0123456789':
            kind = log['digit_ends'][cmap[ord(ch)]]
            top, bottom = ends(ch)
            want = ((flat_ref if kind['top'] == 'flat' else round_ref)[0],
                    (flat_ref if kind['bottom'] == 'flat' else round_ref)[1])
            digit_rows[ch] = {'top': top, 'bottom': bottom, 'kind': kind, 'want': want}
            check(abs(top - want[0]) <= 1 and abs(bottom - want[1]) <= 1,
                  '%s digit %s ends %s, want %s' % (style, ch, (top, bottom), want))
        r['digit_ends'] = digit_rows
        # 4.93 outline defects (inherited_fixes.py): none left
        meant = inherited_fixes.meant_counters(new)
        wrong = {n: inherited_fixes.reversed_contours(glyf[n], glyf, n in meant)
                 for n in new.getGlyphOrder() if glyf[n].numberOfContours > 1}
        wrong = {n: v for n, v in wrong.items() if v}
        r['reversed_contours_left'] = wrong
        check(not wrong, '%s reversed contours left %s' % (style, list(wrong)[:5]))
        ref_style = 'Italic' if style.endswith('Italic') else 'Regular'
        ref_glyf = TTFont(OUT / 'ttf' / ('FridayMono-%s.ttf' % ref_style))['glyf']
        for cp in (0x402, 0x212E):
            check(glyf[cmap[cp]].numberOfContours == ref_glyf[cmap[cp]].numberOfContours,
                  '%s U+%04X contours %d' % (style, cp, glyf[cmap[cp]].numberOfContours))
        strokes = stroke_check(old, new)
        r['strokes_old_new'] = strokes
        bad_strokes = strokes_kept(strokes, h['stroke'])
        check(not bad_strokes, '%s strokes changed %s' % (style, bad_strokes))
        tents = sum(count_tents(glyf[n], glyf, (1,)) for n in new.getGlyphOrder())
        r['faceted_extrema_left'] = tents
        check(tents == 0, '%s tents left %d' % (style, tents))
        widths = {new['hmtx'][cmap[cp]][0] for cp in cmap}
        r['advances'] = sorted(widths)
        check(widths <= {0, 600}, '%s advances %s' % (style, widths))

        # box drawing fits the line box exactly
        for cp in (0x2502, 0x2551, 0x2588, 0x253C):
            g = glyf[cmap[cp]]
            g.recalcBounds(glyf)
            check((g.yMin, g.yMax) == (DESCENT, ASCENT), '%s U+%04X y %s' % (style, cp, (g.yMin, g.yMax)))
        for cp in (0x2500, 0x2550, 0x253C, 0x2588):
            g = glyf[cmap[cp]]
            check((g.xMin, g.xMax) == (0, 600), '%s U+%04X x %s' % (style, cp, (g.xMin, g.xMax)))
        r['box_join_gaps'] = box_joins(path)
        check(not r['box_join_gaps'], '%s box gaps %s' % (style, r['box_join_gaps'][:4]))

        # rendering
        h = heights(path)
        r['round_vs_flat_px'] = {px: v for px, v in h.items() if v['caps'] or v['lower']}
        bad24 = [px for px, v in h.items() if px <= 24 and (v['caps'] or v['lower'])]
        check(not bad24, '%s round letters off at %s px' % (style, bad24))
        r['digits_aligned'] = rehint.report(str(path))
        check(r['digits_aligned'], '%s digits' % style)
        errors, empty = render_all(path, cmap, glyf)
        r['render_errors'], r['render_empty'] = errors, empty
        check(not errors and not empty, '%s render %s %s' % (style, errors[:3], empty[:3]))

        # metrics
        hh, os2, post = new['hhea'], new['OS/2'], new['post']
        r['hhea'] = [hh.ascent, hh.descent, hh.lineGap]
        r['typo'] = [os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap]
        r['win'] = [os2.usWinAscent, os2.usWinDescent]
        r['line_centre_minus_cap_centre'] = (hh.ascent + hh.descent) / 2 - os2.sCapHeight / 2
        check(r['hhea'] == r['typo'] == [ASCENT, DESCENT, 0], '%s line metrics' % style)
        ul = [layout(new, p, d) for p in range(8, 25) for d in (96, 120, 144, 192)]
        r['double_underline_separate'] = sum(c['visible_gap'] >= 1 for c in ul)
        check(r['double_underline_separate'] == len(ul), '%s double underline' % style)
        for attr in ('usWeightClass', 'fsSelection'):
            check(getattr(os2, attr) == getattr(old['OS/2'], attr), '%s %s' % (style, attr))
        for nid in (1, 2, 4, 6, 16, 17):
            check(new['name'].getDebugName(nid) == old['name'].getDebugName(nid), '%s name %d' % (style, nid))
        r['names'] = {nid: new['name'].getDebugName(nid) for nid in (1, 2, 3, 4, 5, 6, 16, 17, 19)}
        check(post.isFixedPitch == 1 and os2.panose.bProportion == 9, '%s monospace flags' % style)
        r['features'] = sorted({f.FeatureTag for t in ('GSUB', 'GPOS') for f in new[t].table.FeatureList.FeatureRecord})
        r['shaping'] = shaping(path, cmap)
        s = r['shaping']
        check(s['decomposed_not_one_cell'] == 0, '%s decomposed sequences' % style)
        check(s['zero'] != s['zero_ss01'] and s['zero_ss01'] == s['zero_cv01'], '%s zero switch' % style)
        # woff2
        w = TTFont(OUT / 'web' / ('FridayMono-%s.woff2' % style))
        new = TTFont(path)                       # fresh copy; the checks above recalculated bounds
        glyf = new['glyf']
        same = all(w.getTableData(t) == new.getTableData(t) for t in new.keys()
                   if t not in ('GlyphOrder', 'head', 'loca', 'glyf', 'hmtx', 'DSIG'))
        def outline(table, name):
            g = table[name]
            coords, ends, flags = g.getCoordinates(table)
            program = g.program.getBytecode() if hasattr(g, 'program') and g.program else b''
            return list(coords), list(ends), [f & 1 for f in flags], program
        same = same and all(outline(w['glyf'], n) == outline(glyf, n) for n in new.getGlyphOrder())
        r['woff2_matches_ttf'] = same
        check(same, '%s woff2' % style)
        report['styles'][style] = r
        print('%-15s %4d chars  tents %d  box gaps %d  round-vs-flat sizes %d  digits %s'
              % (style, len(cmap), tents, len(r['box_join_gaps']), len(r['round_vs_flat_px']),
                 r['digits_aligned']), flush=True)
    report['failures'] = FAIL
    (REPORTS / 'validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    print('failures:', len(FAIL))
    for f in FAIL[:40]:
        print('  ', f)
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
