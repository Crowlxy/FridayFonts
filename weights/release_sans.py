"""Friday Sans / Friday Sans UI 2.5: the RC3 candidates under their release names.

Run with InoriMono-v3-build/.venv/bin/python FridayFonts/weights/release_sans.py

Regular / Medium / Bold are the Windows-checked RC3 files from
FridayFonts-WindowsTest/shipping-audit/rc3 ("WinProof Sans RC3" /
"WinProof Sans UI RC3").  Light / SemiBold are the same chain replayed in
FridayFonts-WindowsTest-weights.  Only the name table and head revision are
rewritten; every other table is asserted byte-identical to the RC3 input.
"""
from pathlib import Path
import hashlib, json, shutil

HERE = Path(__file__).resolve().parent
FF = HERE.parent
ROOT = FF.parent
OUT = FF / 'sans/dist-2.5'
VERSION, REVISION = '2.500', 2.5
SOURCES = {'Light': ROOT / 'FridayFonts-WindowsTest-weights/shipping-audit/rc3/fonts',
           'SemiBold': ROOT / 'FridayFonts-WindowsTest-weights/shipping-audit/rc3/fonts'}
for s in ('Regular', 'Medium', 'Bold'):
    SOURCES[s] = ROOT / 'FridayFonts-WindowsTest/shipping-audit/rc3/fonts'
ORDER = ['Light', 'Regular', 'Medium', 'SemiBold', 'Bold']
WEIGHT = {'Light': 300, 'Regular': 400, 'Medium': 500, 'SemiBold': 600, 'Bold': 700}
FAMILIES = [('sans', 'Friday Sans', 'Friday Sans 2.5: proportional Japanese text face (Inter + Noto Sans CJK JP + hand-drawn kana). Windows RC3 candidate promoted to release; Light and SemiBold added.'),
            ('ui', 'Friday Sans UI', 'Friday Sans UI 2.5: Friday Sans sized and spaced for interface text. Windows RC3 candidate promoted to release; Light and SemiBold added.')]
from fontTools.ttLib import TTFont


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def names(f, family, style, description):
    ps = family.replace(' ', '') + '-' + style
    legacy = (family, style) if style in ('Regular', 'Bold') else (family + ' ' + style, 'Regular')
    values = {1: legacy[0], 2: legacy[1], 3: f'{VERSION};FridayProject;{ps}',
              4: family if style == 'Regular' else family + ' ' + style,
              5: 'Version ' + VERSION, 6: ps, 16: family, 17: style, 10: description,
              19: family + ' 日本語 English 𠮷野家'}
    for rec in list(f['name'].names):
        if rec.nameID in values:
            rec.string = values[rec.nameID].encode(rec.getEncoding(), errors='replace')
    for nid, value in values.items():
        f['name'].setName(value, nid, 3, 1, 0x409)
    f['head'].fontRevision = REVISION


def main():
    for d in ('ttf', 'web', 'licenses', 'reports'):
        (OUT / d).mkdir(parents=True, exist_ok=True)
    rows, css = [], []
    for key, family, description in FAMILIES:
        for style in ORDER:
            source = SOURCES[style] / f'{key}-RC3-{style}.ttf'
            f = TTFont(source, recalcTimestamp=False)
            before = TTFont(source, recalcTimestamp=False)
            assert f['OS/2'].usWeightClass == WEIGHT[style], (source, f['OS/2'].usWeightClass)
            assert bool(f['OS/2'].fsSelection & 32) == (style == 'Bold')
            names(f, family, style, description)
            stem = family.replace(' ', '') + '-' + style
            path, web = OUT / 'ttf' / (stem + '.ttf'), OUT / 'web' / (stem + '.woff2')
            f.save(path); f.flavor = 'woff2'; f.save(web)
            cur, w = TTFont(path, recalcTimestamp=False), TTFont(web)
            before['head'].fontRevision = cur['head'].fontRevision
            before['head'].checkSumAdjustment = cur['head'].checkSumAdjustment
            for tag in before.keys():
                if tag not in ('GlyphOrder', 'name'):
                    assert before.getTableData(tag) == cur.getTableData(tag), (stem, tag)
            for tag in cur.keys():
                if tag not in ('GlyphOrder', 'head', 'glyf', 'loca'):
                    assert cur.getTableData(tag) == w.getTableData(tag), (stem, tag, 'woff2')
            for n in cur.getGlyphOrder():
                assert cur['glyf'][n].getCoordinates(cur['glyf']) == w['glyf'][n].getCoordinates(w['glyf'])
            rows.append(dict(family=family, style=style, weight=WEIGHT[style], ttf=f'ttf/{stem}.ttf',
                             woff2=f'web/{stem}.woff2', sha256=sha(path), woff2_sha256=sha(web),
                             source=str(source.relative_to(ROOT)), source_sha256=sha(source),
                             source_family=before['name'].getDebugName(16), glyphs=len(cur.getGlyphOrder()),
                             codepoints=len(cur.getBestCmap()), units_per_em=cur['head'].unitsPerEm))
            css.append('@font-face{font-family:"%s";src:url("%s.woff2") format("woff2");font-weight:%d;font-style:normal;font-display:swap;}'
                       % (family, stem, WEIGHT[style]))
            print(stem, 'from', source.name, flush=True)
            for x in (f, before, cur, w):
                x.close()
    (OUT / 'font-manifest.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    (OUT / 'web/friday-sans.css').write_text('\n'.join(css) + '\n')
    shutil.copy2(FF / 'sans/OFL.txt', OUT / 'OFL.txt')
    shutil.copytree(ROOT / 'FridayFonts-WindowsTest/licenses', OUT / 'licenses', dirs_exist_ok=True)
    print('Sans 2.5 faces:', len(rows))


if __name__ == '__main__':
    main()
