"""Derive Mono/Plain and JP/JP Plain from the corrected RC3 masters.

Run with InoriMono-v3-build/.venv/bin/python FridayFonts/scripts/build_mono_49.py.
Reference OTFs are inspected only; no reference outline is copied.
"""
from pathlib import Path
from collections import Counter
import argparse, copy, hashlib, json, unicodedata as ud, time
import brotli
import fontTools
from fontTools.ttLib import TTFont
from fontTools import subset
from fontTools.unicodedata import block, script
from fontTools.ttLib.tables import otTables
from build_cache import ArtifactCache
import italic_rc3

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'FridayFonts/releases/archive/mono-4.91'
REF = ROOT / 'comparisons/mono-coverage-2026-10-04'
RC3 = ROOT / 'FridayFonts-WindowsTest/shipping-audit/rc3/fonts'
_compress = brotli.compress
def web_compress(data, **kwargs):
    kwargs['quality'] = 6
    return _compress(data, **kwargs)
brotli.compress = web_compress

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def coverage():
    sources = json.loads((REF / 'reference-sources.json').read_text())
    sources.append(dict(file='SF-Mono-Regular.otf', local='Source/SFMonoFonts/SF Mono Fonts/SF-Mono-Regular.otf', url='https://developer.apple.com/fonts/'))
    votes, rows = Counter(), []
    for s in sources:
        p = ROOT / s['local'] if 'local' in s else REF / 'references' / s['file']
        f = TTFont(p)
        assert f.sfntVersion == 'OTTO' and 'CFF ' in f, p
        cm = f.getBestCmap(); votes.update(cm.keys())
        rows.append(dict(**s, actual_sha256=sha(p), family=f['name'].getDebugName(1),
                         version=f['name'].getDebugName(5), codepoints=len(cm),
                         blocks=dict(sorted(Counter(block(c) for c in cm).items())),
                         scripts=dict(sorted(Counter(script(c) for c in cm).items())),
                         widths=dict(Counter(f['hmtx'][n][0] for n in cm.values()))))
        f.close()
    keep = {c for c, v in votes.items() if v >= 3 and script(c) in ('Latn','Grek','Cyrl','Zyyy','Zinh')
            and not 0xE000 <= c <= 0xF8FF}
    # Complete the common Latin Extended-A block; include decomposition inputs
    # so retained accented letters continue to work without NFC normalization.
    extras = set(range(0x100, 0x180))
    keep |= extras
    for c in list(keep):
        keep.update(map(ord, ud.normalize('NFD', chr(c))))
    keep.add(0xFE00)  # Standardized zero + VS1: slashed zero in both families.
    base = TTFont(RC3 / 'mono-RC3-Regular.ttf').getBestCmap()
    assert not (keep - set(base) - {0xFE00}), keep - set(base)
    report = dict(references=rows, majority_threshold=3, majority_codepoints=1086,
                  policy='At least 3 of 5 OTF families; complete Latin Extended-A and canonical decomposition inputs; zero VS1. No borrowed outlines.',
                  included_codepoints=sorted(keep), additions_to_majority=sorted(c for c in keep if votes[c] < 3),
                  included_blocks=dict(sorted(Counter(block(c) for c in keep if c in base).items())),
                  excluded_blocks=dict(sorted(Counter(block(c) for c in base if c not in keep).items())),
                  votes={f'U+{c:04X}':votes[c] for c in sorted(set(base)|set(votes))})
    (REF / 'coverage-comparison.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    return keep, report

def plain(f):
    for tag in ('glyf','hmtx','vmtx'):
        f[tag]['zero'], f[tag]['zero.alt'] = f[tag]['zero.alt'], f[tag]['zero']
    for t in f['cmap'].tables:
        if t.format == 14:
            t.uvsDict[0xFE00] = [(c, 'zero.alt' if c == 0x30 else n) for c,n in t.uvsDict[0xFE00]]
    # Reuse ss01's lookup. Existing mark/ccmp/vertical layout is untouched.
    table = f['GSUB'].table
    ss = next(r for r in table.FeatureList.FeatureRecord if r.FeatureTag == 'ss01')
    record = otTables.FeatureRecord(); record.FeatureTag = 'zero'; record.Feature = copy.deepcopy(ss.Feature)
    index = len(table.FeatureList.FeatureRecord); table.FeatureList.FeatureRecord.append(record)
    # zero sorts after vrt2, so existing feature indices do not change.
    assert [r.FeatureTag for r in table.FeatureList.FeatureRecord] == sorted(r.FeatureTag for r in table.FeatureList.FeatureRecord)
    table.FeatureList.FeatureCount = len(table.FeatureList.FeatureRecord)
    for sr in table.ScriptList.ScriptRecord:
        systems = ([sr.Script.DefaultLangSys] if sr.Script.DefaultLangSys else []) + [r.LangSys for r in sr.Script.LangSysRecord]
        for lang in systems:
            if any(table.FeatureList.FeatureRecord[i].FeatureTag == 'ss01' for i in lang.FeatureIndex):
                lang.FeatureIndex.append(index); lang.FeatureCount = len(lang.FeatureIndex)

def rename(f, family, style):
    ps = family.replace(' ', '') + '-' + style
    subfamily=style.replace('MediumItalic','Medium Italic').replace('BoldItalic','Bold Italic')
    legacy_family=family+' Medium' if style.startswith('Medium') else family
    legacy_style=('Italic' if 'Italic' in style else 'Regular') if style.startswith('Medium') else subfamily
    labels = {1: legacy_family, 2:legacy_style,
              3:'FridayProject;4.910;'+ps, 4:family+' '+subfamily, 5:'Version 4.910', 6:ps, 16:family, 17:subfamily,
              10:'Mono RC3 repair policy, upright and italic. Coverage and validation: see packaged report.'}
    f['head'].fontRevision = 4.91
    for rec in f['name'].names:
        if rec.nameID in labels: rec.string = labels[rec.nameID].encode(rec.getEncoding(), errors='replace')
    for nid, val in labels.items(): f['name'].setName(val, nid, 3, 1, 0x409)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--no-cache',action='store_true');args=ap.parse_args()
    started=time.perf_counter()
    cache=ArtifactCache(ROOT/'FridayFonts/.build-cache/mono',enabled=not args.no_cache)
    tools=dict(fontTools=fontTools.__version__,brotli=brotli.__version__,freetype=italic_rc3.raster.version)
    keep, comparison = coverage()
    for folder in ('ttf', 'web', 'reports', 'licenses'):
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    manifest, css = [], []
    for style in ('Regular','Medium','Bold','Italic','MediumItalic','BoldItalic'):
        if 'Italic' in style:
            upright={'Italic':'Regular','MediumItalic':'Medium','BoldItalic':'Bold'}[style]
            source=italic_rc3.DEST/'ttf'/f'mono-RC3-{style}.ttf'
            report=italic_rc3.DEST/f'{style}-audit.json'
            deps=[ROOT/f'FridayFonts/releases/archive/mono-v48/ttf/FridayMono-{style}.ttf',
                  ROOT/f'FridayFonts/releases/archive/mono-v48/ttf/FridayMono-{upright}.ttf',RC3/f'mono-RC3-{upright}.ttf',
                  Path(italic_rc3.__file__),Path(__file__).parent/'build_cache.py',
                  ROOT/'FridayFonts-WindowsTest/windows-lab/tools/build_candidate.py',
                  ROOT/'FridayFonts-WindowsTest/tools/build_kanji_guard_trial.py',
                  ROOT/'FridayFonts-WindowsTest/tools/font_raster.py']
            cache.run('italic-rc3-'+style,deps,tools,[source,report],lambda:italic_rc3.build(style,source,report))
        else:
            source = RC3 / f'mono-RC3-{style}.ttf'
        for jp in (True, False):
            for is_plain in ((False, True) if jp else (False,)):
                family = 'Friday Mono' + (' Plain' if is_plain else '') + (' JP' if jp else '')
                stem = family.replace(' ', '') + '-' + style
                path = OUT / 'ttf' / (stem+'.ttf'); web = OUT / 'web' / (stem+'.woff2')
                weight = 700 if 'Bold' in style else (500 if 'Medium' in style else 400)
                def build_face():
                    f = TTFont(source, recalcTimestamp=False)
                    if is_plain: plain(f)
                    if not jp:
                        options = subset.Options()
                        options.layout_features = ['*']; options.name_IDs = ['*']; options.name_legacy = True
                        options.name_languages = ['*']; options.notdef_glyph = True; options.notdef_outline = True
                        options.glyph_names = True
                        options.recalc_timestamp = False; options.hinting = True
                        options.no_subset_tables += ['ltag']
                        sub = subset.Subsetter(options=options); sub.populate(unicodes=keep); sub.subset(f)
                        # Layout closure may keep encoded aliases of surviving glyphs.
                        # Keep the advertised Unicode coverage explicit.
                        for table in f['cmap'].tables:
                            if table.isUnicode() and table.format != 14:
                                table.cmap = {c:n for c,n in table.cmap.items() if c in keep}
                        f['OS/2'].recalcUnicodeRanges(f)
                        assert set(f.getBestCmap()) == keep - {0xFE00}
                        assert all(f['hmtx'][n][0] in (0,600) for n in f.getBestCmap().values())
                        assert not any(script(c) in ('Hani','Hira','Kana','Hang','Bopo') for c in f.getBestCmap())
                        assert not any(0xFF00 <= c <= 0xFFEF for c in f.getBestCmap())
                        # Vertical substitutions have no purpose in the non-CJK family.
                        assert not any(r.FeatureTag in ('vert','vrt2') for r in f['GSUB'].table.FeatureList.FeatureRecord)
                    rename(f, family, style)
                    f.save(path)
                    f.flavor = 'woff2'; f.save(web)
                    t = TTFont(path); w = TTFont(web)
                    for tag in ('cmap','GSUB','GPOS','GDEF','OS/2','hmtx','vmtx','fpgm','prep','cvt '):
                        if tag in t: assert t.getTableData(tag) == w.getTableData(tag), (stem, tag)
                    for n in t.getGlyphOrder():
                        assert t['glyf'][n].getCoordinates(t['glyf']) == w['glyf'][n].getCoordinates(w['glyf'])
                        assert getattr(t['glyf'][n], 'program', None) == getattr(w['glyf'][n], 'program', None)
                    record=dict(family=family, style=style, weight=weight, jp=jp, plain=is_plain,
                                         ttf=str(path.relative_to(OUT)), woff2=str(web.relative_to(OUT)),
                                         sha256=sha(path), woff2_sha256=sha(web), source=str(source.relative_to(ROOT)),
                                         source_sha256=sha(source), codepoints=len(t.getBestCmap()), glyphs=len(t.getGlyphOrder()))
                    f.close(); t.close(); w.close()
                    return record
                settings=dict(**tools,style=style,jp=jp,plain=is_plain,coverage=sorted(keep) if not jp else None,version='4.910')
                record=cache.run('face-'+stem,[source,Path(__file__),Path(__file__).parent/'build_cache.py'],settings,[path,web],build_face)
                manifest.append(record)
                css.append('@font-face{font-family:"%s";src:url("%s.woff2") format("woff2");font-weight:%d;font-style:%s;font-display:swap;}' % (family,stem,weight,'italic' if 'Italic' in style else 'normal'))
                print(stem,record['codepoints'],flush=True)
    (OUT/'font-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    (OUT/'web/friday-mono.css').write_text('\n'.join(css)+'\n')
    (OUT/'reports/coverage-comparison.json').write_text(json.dumps(comparison, ensure_ascii=False, indent=2)+'\n')
    (OUT/'reports/build-cache-run.json').write_text(json.dumps(dict(seconds=round(time.perf_counter()-started,4),events=cache.events),indent=2)+'\n')

if __name__ == '__main__': main()
