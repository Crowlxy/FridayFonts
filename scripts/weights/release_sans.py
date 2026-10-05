"""Friday Sans / Friday Sans UI 2.5: the RC3 candidates under their release names.

Run with InoriMono-v3-build/.venv/bin/python FridayFonts/scripts/weights/release_sans.py

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
ROOT = FF.parents[1]
OUT = FF.parent / 'releases/sans-2.5'
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
import pickle, sys
sys.path.insert(0, str(FF)); sys.path.insert(0, str(FF / 'tools'))
import shapes

# Friday Sans 1.1 refit every Japanese glyph whose ink crossed its cell as if
# it were a proportional Noto symbol (advance = ink + 100, centred).  The
# hand-drawn ぶ ぷ cross x=0 by 2-10 units once thickened, so Medium and Bold
# shipped them 1064-1083 wide and about 50 units to the right, in their
# vertical forms too.  They go back to the 1000 cell at the CJK master's own
# position; the centre mark anchor moves with them.  Sans UI refits kana to
# its own widths and is unaffected; Light / SemiBold were built without it.
WIDE_KANA = {'jp.uni3076': 'jp.glyph65210', 'jp.uni3077': 'jp.glyph65211'}
CJK_MASTER = str(ROOT / 'InoriMono-v3-build/sans/work/cjk-%s.pkl')


def repair_wide_kana(f, style):
    """Return the glyphs changed; asserts the shipped state it repairs."""
    master = pickle.load(open(CJK_MASTER % style, 'rb'))
    glyf, hmtx = f['glyf'], f['hmtx']
    changed, shifts = [], {}
    for name, vertical in WIDE_KANA.items():
        rec, cell = master['glyphs'][name[3:]]
        assert cell == 1000
        target = round(shapes.bbox(rec)[0])
        g = glyf[name]; g.recalcBounds(glyf)
        adv, lsb = hmtx[name]
        if adv == 1000:
            continue
        assert lsb == g.xMin == 50 and target < 0 and hmtx[vertical] == (1000, 50), (style, name)
        dx = target - g.xMin
        for n in (name, vertical):
            h = glyf[n]
            assert not h.isComposite() and not getattr(h, 'program', None) or not h.program.getBytecode()
            h.coordinates.translate((dx, 0)); h.recalcBounds(glyf)
            hmtx[n] = (1000, h.xMin)
            changed.append(n)
        shifts[name] = dx
    if not shifts:
        return []
    moved = 0
    for lookup in f['GPOS'].table.LookupList.Lookup:
        for st in lookup.SubTable:
            t = st.ExtSubTable if lookup.LookupType == 9 else st
            if getattr(t, 'LookupType', lookup.LookupType) != 4:
                continue
            for name, record in zip(t.BaseCoverage.glyphs, t.BaseArray.BaseRecord):
                if name in shifts:
                    for anchor in record.BaseAnchor:
                        # The dakuten anchor sits at a fixed x for every kana;
                        # only the centred one followed the refit.
                        if anchor is not None and anchor.XCoordinate != 940:
                            anchor.XCoordinate += shifts[name]; moved += 1
    assert moved == len(shifts), (style, moved)
    return changed


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
            repaired = repair_wide_kana(f, style) if key == 'sans' and style in ('Medium', 'Bold') else []
            assert len(repaired) == (4 if key == 'sans' and style in ('Medium', 'Bold') else 0), (key, style, repaired)
            names(f, family, style, description)
            stem = family.replace(' ', '') + '-' + style
            path, web = OUT / 'ttf' / (stem + '.ttf'), OUT / 'web' / (stem + '.woff2')
            f.save(path); f.flavor = 'woff2'; f.save(web)
            cur, w = TTFont(path, recalcTimestamp=False), TTFont(web)
            before['head'].fontRevision = cur['head'].fontRevision
            before['head'].checkSumAdjustment = cur['head'].checkSumAdjustment
            touched = {'glyf', 'loca', 'hmtx', 'GPOS', 'hhea', 'head'} if repaired else set()
            for tag in before.keys():
                if tag not in ('GlyphOrder', 'name') and tag not in touched:
                    assert before.getTableData(tag) == cur.getTableData(tag), (stem, tag)
            if repaired:
                bg, cg = before['glyf'], cur['glyf']
                diff = [n for n in cur.getGlyphOrder()
                        if bg[n].getCoordinates(bg)[0] != cg[n].getCoordinates(cg)[0] or before['hmtx'][n] != cur['hmtx'][n]]
                assert sorted(diff) == sorted(repaired), (stem, diff)
                assert all(cur['hmtx'][n][0] == 1000 for n in repaired)
            for tag in cur.keys():
                if tag not in ('GlyphOrder', 'head', 'glyf', 'loca'):
                    assert cur.getTableData(tag) == w.getTableData(tag), (stem, tag, 'woff2')
            for n in cur.getGlyphOrder():
                assert cur['glyf'][n].getCoordinates(cur['glyf']) == w['glyf'][n].getCoordinates(w['glyf'])
            rows.append(dict(family=family, style=style, weight=WEIGHT[style], ttf=f'ttf/{stem}.ttf',
                             woff2=f'web/{stem}.woff2', sha256=sha(path), woff2_sha256=sha(web),
                             source=str(source.relative_to(ROOT)), source_sha256=sha(source),
                             source_family=before['name'].getDebugName(16), glyphs=len(cur.getGlyphOrder()),
                             repaired_glyphs=repaired,
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
