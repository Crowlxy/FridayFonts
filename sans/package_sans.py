"""Package and seal Friday Sans 1.0 from the hinted faces in fonts-hinted/.

Same allowlist and checks as Friday Mono's package_v48.py: TTF + WOFF2 with a
lossless roundtrip check, licences, manifests, SHA256SUMS and a zip.
"""
import hashlib, json, shutil, zipfile
from pathlib import Path
from fontTools.ttLib import TTFont
import brotli

_original_compress = brotli.compress
def _web_compress(data, **kwargs):
    kwargs["quality"] = 6
    return _original_compress(data, **kwargs)
brotli.compress = _web_compress

VERSION = '1.0'
S = Path(__file__).resolve().parent
R = S.parent
SRC = R.parent / 'Source'
D = S / ('dist-%s' % VERSION)
if D.exists():
    shutil.rmtree(D)
T, W, L = D / 'ttf', D / 'web', D / 'licenses'
for p in (T, W, L):
    p.mkdir(parents=True)
shutil.copyfile(S / 'OFL.txt', D / 'OFL.txt')
shutil.copyfile(SRC / 'Inter/Inter-4.1/LICENSE.txt', L / 'Inter-OFL.txt')
noto = TTFont(SRC / 'noto-cjk/NotoSansCJKjp-VF.ttf')
notice = (noto['name'].getDebugName(0) + '\n\n' + noto['name'].getDebugName(13) + '\n'
          + noto['name'].getDebugName(14) + '\n\n')
body = (S / 'OFL.txt').read_text().split('SIL OPEN FONT LICENSE Version', 1)[1]
(L / 'NotoSansCJK-OFL.txt').write_text(notice + 'SIL OPEN FONT LICENSE Version' + body)

files = sorted((S / 'fonts-hinted').glob('FridaySans-*.ttf'))
assert [p.name for p in files] == ['FridaySans-Bold.ttf', 'FridaySans-Medium.ttf',
                                   'FridaySans-Regular.ttf'], files
css = []
for p in files:
    f = TTFont(p)
    assert len(f['cvt '].values) >= f['maxp'].maxTwilightPoints + 4, (p.name, 'no CJK hints')
    assert 'fpgm' in f and 'prep' in f, (p.name, 'no Latin hints')
    shutil.copyfile(p, T / p.name)
    f.flavor = 'woff2'; f.save(W / (p.stem + '.woff2'))
    # Raw table bytes first: once a table is decompiled, getTableData
    # recompiles it, and the name table's string pool need not come back in
    # the order the build wrote it.
    w = TTFont(W / (p.stem + '.woff2'))
    f = TTFont(p)
    for tag in ('GSUB', 'GPOS', 'GDEF', 'name', 'OS/2', 'vmtx', 'fpgm', 'prep', 'cvt '):
        assert w.getTableData(tag) == f.getTableData(tag), (p.name, tag)
    w.ensureDecompiled()
    assert w.getBestCmap() == f.getBestCmap()
    assert w['hmtx'].metrics == f['hmtx'].metrics
    for n in f.getGlyphOrder():
        a = f['glyf'][n]; b = w['glyf'][n]
        assert a.numberOfContours == b.numberOfContours
        if a.numberOfContours > 0:
            assert list(a.coordinates) == list(b.coordinates)
    weight = 700 if 'Bold' in p.stem else (500 if 'Medium' in p.stem else 400)
    css.append('@font-face {\n  font-family: "Friday Sans";\n  src: url("%s.woff2") format("woff2"), '
               'url("../ttf/%s") format("truetype");\n  font-weight: %s;\n  font-style: normal;\n'
               '  font-display: swap;\n}\n' % (p.stem, p.name, weight))
(W / 'friday-sans.css').write_text('/* Friday Sans %s — SIL OFL 1.1; see ../OFL.txt */\n' % VERSION
                                   + '\n'.join(css))
(D / 'font-manifest.json').write_text(json.dumps(
    [{'file': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in files],
    indent=2) + '\n')
shutil.copyfile(S / ('RELEASE-%s.md' % VERSION), D / 'README.md')
sources = [{'source': str(p.relative_to(R.parent)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
           for p in [SRC / 'Inter/Inter-4.1/InterVariable.ttf', SRC / 'noto-cjk/NotoSansCJKjp-VF.ttf',
                     R / 'drawings/vector-masters.json', R / 'drawings/approved-hand-outlines.json']]
(D / 'source-manifest.json').write_text(json.dumps(sources, indent=2) + '\n')

all_files = sorted(p for p in D.rglob('*') if p.is_file() and p.name != 'SHA256SUMS.txt')
for p in all_files:
    assert p.suffix in {'.ttf', '.woff2', '.css', '.txt', '.md', '.json'}, p
    assert p.name != '.DS_Store' and 'SF' not in p.name and 'Hiragino' not in p.name, p
(D / 'SHA256SUMS.txt').write_text(''.join(
    hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.relative_to(D).as_posix() + '\n'
    for p in all_files))
archive = S / ('FridaySans-%s.zip' % VERSION)
with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for p in sorted(D.rglob('*')):
        if p.is_file():
            z.write(p, Path('FridaySans-%s' % VERSION) / p.relative_to(D))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert sum(n.endswith('.ttf') for n in z.namelist()) == 3
    assert sum(n.endswith('.woff2') for n in z.namelist()) == 3
(S / (archive.name + '.sha256')).write_text(
    hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')
print('Sealed', archive.name, archive.stat().st_size, 'bytes; WOFF2 roundtrip, ZIP CRC and counts verified')
