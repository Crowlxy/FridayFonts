"""Friday Mono 4.93: the 4.92 faces plus Light and SemiBold (upright and italic).

Run with InoriMono-v3-build/.venv/bin/python FridayFonts/weights/release_mono.py
after build_weights.py has produced the RC3 uprights in the work tree.

New faces take exactly the 4.91 -> 4.92 route of the shipped ones:
  italic_rc3.build      the RC3 policy replayed on the independently hinted italic
  build_mono_49         JP / Plain JP / no-JP derivation, coverage and checks
  build_mono_492        hhea/typo descender -120 -> -400 (Windows Terminal)
The 18 shipped 4.92 faces are carried over with only the version (head
revision, name IDs 3/5/10) changed, which is asserted table by table.
"""
from pathlib import Path
import hashlib, json, shutil, sys

HERE = Path(__file__).resolve().parent
FF = HERE.parent
ROOT = FF.parent
BW = FF / 'build-weights'
WS = ROOT / 'FridayFonts-WindowsTest-weights'
OUT = FF / 'dist-mono-4.93'
sys.path.insert(0, str(FF))
sys.path.insert(0, str(HERE))
from build_weights import load

VERSION, REVISION = '4.930', 4.93
NEW = ['Light', 'SemiBold', 'LightItalic', 'SemiBoldItalic']
UPRIGHT = {'Italic': 'Regular', 'MediumItalic': 'Medium', 'BoldItalic': 'Bold',
           'LightItalic': 'Light', 'SemiBoldItalic': 'SemiBold'}
WEIGHT = {'Light': 300, 'Regular': 400, 'Medium': 500, 'SemiBold': 600, 'Bold': 700}
DESCRIPTION = ('Friday Mono 4.93: Light and SemiBold added (upright and italic), built by the '
               '4.92 route. Glyph data of Regular/Medium/Bold unchanged from 4.92.')

italic_rc3 = load(FF / 'italic_rc3.py', [
    ("DEST=ROOT/'FridayFonts/rc3-italic'", "DEST=ROOT/'FridayFonts/build-weights/rc3-italic'"),
    ("    source=ROOT/f'FridayFonts/dist-v48/ttf/FridayMono-{style}.ttf'",
     "    source=ROOT/f'FridayFonts/build-weights/mono-v48/FridayMono-{style}.ttf'"),
    ("    upright_style={'Italic':'Regular','MediumItalic':'Medium','BoldItalic':'Bold'}[style]",
     "    upright_style={'LightItalic':'Light','SemiBoldItalic':'SemiBold'}[style]"),
    ("    old=TTFont(ROOT/f'FridayFonts/dist-v48/ttf/FridayMono-{upright_style}.ttf')",
     "    old=TTFont(ROOT/f'FridayFonts/build-weights/mono-v48/FridayMono-{upright_style}.ttf')"),
    ("    rc3=TTFont(ROOT/f'FridayFonts-WindowsTest/shipping-audit/rc3/fonts/mono-RC3-{upright_style}.ttf')",
     "    rc3=TTFont(ROOT/f'FridayFonts-WindowsTest-weights/shipping-audit/rc3/fonts/mono-RC3-{upright_style}.ttf')"),
], name='italic_rc3')
sys.modules['italic_rc3'] = italic_rc3
mono49 = load(FF / 'build_mono_49.py', [
    # coverage() rewrites the shipped comparison report; keep it read-only here.
    ("    (REF / 'coverage-comparison.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\\n')\n", ""),
], name='build_mono_49_weights')
mono492 = load(FF / 'build_mono_492.py', name='build_mono_492_weights')
from fontTools.ttLib import TTFont
from fontTools import subset


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def subfamily(style):
    if style == 'Italic':
        return 'Italic'
    return style.replace('Italic', ' Italic')


def ribbi(family, style):
    """Legacy (ID 1/2) names: only Regular/Italic/Bold/Bold Italic may share ID 1."""
    italic = 'Italic' in style
    weight = style.replace('Italic', '') or 'Regular'
    if weight in ('Regular', 'Bold'):
        return family, subfamily(style) if style != 'Italic' else 'Italic'
    return family + ' ' + weight, 'Italic' if italic else 'Regular'


def label(f, family, style, description=DESCRIPTION):
    ps = family.replace(' ', '') + '-' + style
    legacy_family, legacy_style = ribbi(family, style)
    sub = subfamily(style)
    values = {1: legacy_family, 2: legacy_style, 3: f'FridayProject;{VERSION};{ps}',
              4: family + ' ' + sub, 5: 'Version ' + VERSION, 6: ps, 16: family, 17: sub,
              10: description}
    f['head'].fontRevision = REVISION
    for rec in f['name'].names:
        if rec.nameID in values:
            rec.string = values[rec.nameID].encode(rec.getEncoding(), errors='replace')
    for nid, val in values.items():
        f['name'].setName(val, nid, 3, 1, 0x409)


def new_face(source, family, style, keep, jp, is_plain):
    f = TTFont(source, recalcTimestamp=False)
    if is_plain:
        mono49.plain(f)
    if not jp:
        options = subset.Options()
        options.layout_features = ['*']; options.name_IDs = ['*']; options.name_legacy = True
        options.name_languages = ['*']; options.notdef_glyph = True; options.notdef_outline = True
        options.glyph_names = True; options.recalc_timestamp = False; options.hinting = True
        options.no_subset_tables += ['ltag']
        sub = subset.Subsetter(options=options); sub.populate(unicodes=keep); sub.subset(f)
        for table in f['cmap'].tables:
            if table.isUnicode() and table.format != 14:
                table.cmap = {c: n for c, n in table.cmap.items() if c in keep}
        f['OS/2'].recalcUnicodeRanges(f)
        assert set(f.getBestCmap()) == keep - {0xFE00}
        assert all(f['hmtx'][n][0] in (0, 600) for n in f.getBestCmap().values())
        assert not any(r.FeatureTag in ('vert', 'vrt2') for r in f['GSUB'].table.FeatureList.FeatureRecord)
    # 4.92 line metrics, applied the way build_mono_492 applies them.
    assert (f['hhea'].descent, f['OS/2'].sTypoDescender) == (-120, -120)
    assert f['OS/2'].fsSelection & 128
    f['hhea'].descent = f['OS/2'].sTypoDescender = -400
    assert f['OS/2'].usWeightClass == WEIGHT[style.replace('Italic', '') or 'Regular'], (style, f['OS/2'].usWeightClass)
    label(f, family, style)
    return f


def save_pair(f, stem):
    path, web = OUT / 'ttf' / (stem + '.ttf'), OUT / 'web' / (stem + '.woff2')
    f.save(path); f.flavor = 'woff2'; f.save(web); f.flavor = None
    t, w = TTFont(path), TTFont(web)
    for tag in t.keys():
        if tag not in ('GlyphOrder', 'head', 'glyf', 'loca'):
            assert t.getTableData(tag) == w.getTableData(tag), (stem, tag)
    for n in t.getGlyphOrder():
        assert t['glyf'][n].getCoordinates(t['glyf']) == w['glyf'][n].getCoordinates(w['glyf'])
        assert getattr(t['glyf'][n], 'program', None) == getattr(w['glyf'][n], 'program', None)
    predictions = [mono492.layout(t, p, dpi) for dpi in (96, 120, 144, 192) for p in range(8, 25)]
    assert all(r['two_separate_lines'] for r in predictions), stem
    t.close(); w.close()
    return path, web


def main():
    for folder in ('ttf', 'web', 'reports', 'licenses'):
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    keep, _ = mono49.coverage()
    rows, audits = [], []
    # Carried-over 4.92 faces: version only.
    for old in json.loads((FF / 'dist-mono-4.92/font-manifest.json').read_text()):
        source = FF / 'dist-mono-4.92' / old['ttf']
        assert sha(source) == old['sha256']
        f = TTFont(source, recalcTimestamp=False)
        before = TTFont(source, recalcTimestamp=False)
        label(f, old['family'], old['style'])
        path, web = save_pair(f, Path(old['ttf']).stem)
        cur = TTFont(path, recalcTimestamp=False)
        before['head'].fontRevision = cur['head'].fontRevision
        before['head'].checkSumAdjustment = cur['head'].checkSumAdjustment
        for tag in before.keys():
            if tag not in ('GlyphOrder', 'name'):
                assert before.getTableData(tag) == cur.getTableData(tag), (path.name, tag)
        names = lambda x: {(r.nameID, r.platformID, r.platEncID, r.langID): r.toUnicode()
                           for r in x['name'].names if r.nameID not in (3, 5, 10)}
        assert names(before) == names(cur), path.name
        rows.append(dict(old, source=str(source.relative_to(ROOT)), source_sha256=sha(source),
                         sha256=sha(path), woff2_sha256=sha(web)))
        print('carried', path.name, flush=True)
    # New faces.
    for style in NEW:
        if 'Italic' in style:
            source = italic_rc3.DEST / 'ttf' / f'mono-RC3-{style}.ttf'
            report = italic_rc3.DEST / f'{style}-audit.json'
            (italic_rc3.DEST / 'ttf').mkdir(parents=True, exist_ok=True)
            audits.append(italic_rc3.build(style, source, report))
        else:
            source = WS / f'shipping-audit/rc3/fonts/mono-RC3-{style}.ttf'
        for jp in (True, False):
            for is_plain in ((False, True) if jp else (False,)):
                family = 'Friday Mono' + (' Plain' if is_plain else '') + (' JP' if jp else '')
                stem = family.replace(' ', '') + '-' + style
                f = new_face(source, family, style, keep, jp, is_plain)
                path, web = save_pair(f, stem)
                t = TTFont(path)
                rows.append(dict(family=family, style=style, weight=WEIGHT[style.replace('Italic', '') or 'Regular'],
                                 jp=jp, plain=is_plain, ttf=f'ttf/{stem}.ttf', woff2=f'web/{stem}.woff2',
                                 sha256=sha(path), woff2_sha256=sha(web), source=str(source.relative_to(ROOT)),
                                 source_sha256=sha(source), codepoints=len(t.getBestCmap()), glyphs=len(t.getGlyphOrder())))
                t.close()
                print('new', stem, flush=True)
    order = ['Light', 'Regular', 'Medium', 'SemiBold', 'Bold']
    key = lambda r: (r['family'], 'Italic' in r['style'], order.index(r['style'].replace('Italic', '') or 'Regular'))
    rows.sort(key=key)
    assert len(rows) == 30
    (OUT / 'font-manifest.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    css = ['@font-face{font-family:"%s";src:url("%s") format("woff2");font-weight:%d;font-style:%s;font-display:swap;}'
           % (r['family'], Path(r['woff2']).name, r['weight'], 'italic' if 'Italic' in r['style'] else 'normal')
           for r in rows]
    (OUT / 'web/friday-mono.css').write_text('\n'.join(css) + '\n')
    for p in (FF / 'dist-mono-4.92/licenses').glob('*.txt'):
        shutil.copy2(p, OUT / 'licenses' / p.name)
    shutil.copy2(FF / 'OFL.txt', OUT / 'OFL.txt')
    print('Mono 4.93 faces:', len(rows))


if __name__ == '__main__':
    main()
