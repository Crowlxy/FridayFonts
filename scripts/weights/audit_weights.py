"""Weight-ladder audit and proof for the 5-weight Friday families.

Run with InoriMono-v3-build/.venv/bin/python FridayFonts/scripts/weights/audit_weights.py <dist> [<dist> ...]

For every family found in the given dist folders' font-manifest.json:
  - Latin stem (H for Mono, n for Sans), kanji median stem, kana mean stroke
    (2 x area / outline length) and hand-drawn kana stroke relative to their
    kana neighbours, per weight; the ladder must rise monotonically.
  - Every glyph is rendered through FreeType (hinted, interpreter 40 and 35)
    at 9-24 px: no load error, and no glyph with outline ink renders empty.
  - A proof PNG of all weights.
Writes <dist>/reports/weight-audit.json and <dist>/reports/weights-proof-*.png.
"""
from pathlib import Path
import json, statistics, sys
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import DecomposingRecordingPen
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FF = HERE.parent
ROOT = FF.parents[1]
sys.path.insert(0, str(FF)); sys.path.insert(0, str(FF / 'tools'))
sys.path.insert(0, str(ROOT / 'FridayFonts-WindowsTest/tools'))
import shapes
import build_inori_v3 as mono
import font_raster as raster

ORDER = ['Light', 'Regular', 'Medium', 'SemiBold', 'Bold']
HAND = set(mono.HAND_ALL)
KANA = [chr(c) for c in list(range(0x3041, 0x3094)) + list(range(0x30A1, 0x30F5))]
LATIN = 'Hamburgefontsiv 0123456789 {}[]() => != && ||'
JP = '設定を保存しました。日本語とEnglishの混植 とどさざきぎふぶぷやゃ アイウエオ 鬱議'


def rec(f, ch):
    cm = f.getBestCmap()
    if ord(ch) not in cm:
        return None
    gs = f.getGlyphSet(); pen = DecomposingRecordingPen(gs); gs[cm[ord(ch)]].draw(pen)
    return pen.value


def stroke(r):
    length = 0.0
    for poly in shapes._flatten(r):
        for i in range(len(poly)):
            (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % len(poly)]
            length += ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    return 2 * abs(shapes.area(r)) / length if length else 0.0


def measure(path, sans):
    f = TTFont(path)
    k = 1000 / f['head'].unitsPerEm
    out = {}
    latin = rec(f, 'n' if sans else 'H')
    if 'Italic' in path.name:
        latin = shapes.shear(latin, 0.0, pivot_y=mono.SF_CAP / 2, src_angle_deg=float(f['post'].italicAngle))
    out['latin_stem'] = round(shapes.stem_of(latin) * k, 2)
    if ord('日') in f.getBestCmap():
        recs = {}
        for ch in set(mono.KANJI_SAMPLE):
            r = rec(f, ch)
            if r and 'Italic' in path.name:
                r = shapes.shear(r, 0.0, pivot_y=mono.SF_CAP / 2, src_angle_deg=-10.0)
            if r:
                recs[ch] = r
        stems = [shapes.stem_of(r, cuts=shapes.CJK_CUTS) for r in recs.values()]
        out['kanji_stem'] = round(statistics.median([s for s in stems if s]) * k, 2)
        kana = {ch: stroke(rec(f, ch)) * k for ch in KANA if rec(f, ch)}
        plain = [v for ch, v in kana.items() if ch not in HAND]
        out['kana_stroke'] = round(statistics.median(plain), 2)
        out['hand_kana_vs_neighbours'] = {ch: round(kana[ch] / out['kana_stroke'], 3) for ch in sorted(HAND) if ch in kana}
    f.close()
    return out


def render_audit(path):
    f = TTFont(path)
    names = [n for n in f.getGlyphOrder() if f['glyf'][n].numberOfContours != 0]
    order = {n: i for i, n in enumerate(f.getGlyphOrder())}
    face = raster.face(path)
    errors, empty, cases = [], [], 0
    for engine in (35, 40):
        raster.interpreter(engine)
        for px in (9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 24):
            raster.size(face, px)
            for n in names:
                g = f['glyf'][n]
                err, bm = raster.bitmap(face, order[n])
                cases += 1
                if err:
                    errors.append([engine, px, n, err])
                elif bm is None or not bm[0].size or not bm[0].any():
                    # A hairline glyph may legitimately vanish below 12 px.
                    g.recalcBounds(f['glyf'])
                    if px >= 12 and (g.yMax - g.yMin) * px / f['head'].unitsPerEm >= 2 \
                            and (g.xMax - g.xMin) * px / f['head'].unitsPerEm >= 2:
                        empty.append([engine, px, n])
    raster.FT.FT_Done_Face(face)
    raster.interpreter(40)
    f.close()
    return dict(cases=cases, errors=errors[:50], error_count=len(errors), empty=empty[:50], empty_count=len(empty))


def main():
    report = {}
    for dist in map(Path, sys.argv[1:]):
        rows = json.loads((dist / 'font-manifest.json').read_text())
        (dist / 'reports').mkdir(exist_ok=True)
        families = {}
        for r in rows:
            italic = 'Italic' in r['style']
            weight = r['style'].replace('Italic', '') or 'Regular'
            families.setdefault((r['family'], italic), {})[weight] = dist / r['ttf']
        for (family, italic), faces in sorted(families.items()):
            sans = 'Sans' in family
            label = family + (' Italic' if italic else '')
            rows_out = {}
            for w in ORDER:
                if w in faces:
                    rows_out[w] = measure(faces[w], sans)
                    rows_out[w]['render'] = render_audit(faces[w])
                    print(label, w, {k: v for k, v in rows_out[w].items() if k not in ('render', 'hand_kana_vs_neighbours')},
                          'render errors', rows_out[w]['render']['error_count'], 'empty', rows_out[w]['render']['empty_count'], flush=True)
            ladder = {}
            for key in ('latin_stem', 'kanji_stem', 'kana_stroke'):
                seq = [rows_out[w][key] for w in ORDER if w in rows_out and key in rows_out[w]]
                if seq:
                    ladder[key] = dict(values=seq, monotonic=all(a < b for a, b in zip(seq, seq[1:])))
            hand = [v for w in rows_out.values() for v in w.get('hand_kana_vs_neighbours', {}).values()]
            report[label] = dict(weights=rows_out, ladder=ladder,
                                 hand_kana_ratio_range=[min(hand), max(hand)] if hand else None)
            # Proof sheet.
            img = Image.new('L', (2200, 120 + 150 * len(faces)), 255)
            d = ImageDraw.Draw(img)
            d.text((20, 20), label, font=ImageFont.load_default(size=30), fill=0)
            for i, w in enumerate([w for w in ORDER if w in faces]):
                y = 80 + i * 150
                d.text((20, y + 20), w, font=ImageFont.load_default(size=22), fill=90)
                d.text((180, y), LATIN, font=ImageFont.truetype(str(faces[w]), 44), fill=0)
                d.text((180, y + 62), JP if ord('日') in TTFont(faces[w]).getBestCmap() else LATIN.lower(),
                       font=ImageFont.truetype(str(faces[w]), 44), fill=0)
            img.save(dist / 'reports' / ('weights-proof-' + label.replace(' ', '') + '.png'))
        (dist / 'reports/weight-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    bad = [k for k, v in report.items() for key, l in v['ladder'].items() if not l['monotonic']]
    bad += [k for k, v in report.items() for w in v['weights'].values() if w['render']['error_count'] or w['render']['empty_count']]
    print('PROBLEMS:', sorted(set(bad)) if bad else 'none')


if __name__ == '__main__':
    main()
