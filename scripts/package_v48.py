"""Package and seal Friday Mono v48 (the renamed v47; see rename_v48.py).

Same allowlist and checks as package_v47.py + seal_v47.py.  The audit
results are v47's: v48 carries the same glyph, hint and layout bytes, so they
are shipped as they were run, under audit/v47/, and QUALITY-REPORT.md says so.
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

R = Path(__file__).resolve().parent
D = R.parent / 'releases/archive/mono-v48'
if D.exists():
    shutil.rmtree(D)
T, W, L, A = D / 'ttf', D / 'web', D / 'licenses', D / 'audit' / 'v47'
for p in (T, W, L, A):
    p.mkdir(parents=True, exist_ok=True)
shutil.copyfile(R / 'OFL.txt', D / 'OFL.txt')
shutil.copyfile(R.parents[1] / 'Source/Iosevka/LICENSE.md', L / 'Iosevka-OFL.txt')
source = TTFont(R.parent / 'Source/noto-cjk/NotoSansCJKjp-VF.ttf')
notice = (source['name'].getDebugName(0) + '\n\n' + source['name'].getDebugName(13) + '\n'
          + source['name'].getDebugName(14) + '\n\n')
body = (R / 'OFL.txt').read_text().split('SIL OPEN FONT LICENSE Version', 1)[1]
(L / 'NotoSansCJK-OFL.txt').write_text(notice + 'SIL OPEN FONT LICENSE Version' + body)

css = []
files = sorted((R / 'fonts-v48').glob('*.ttf'))
assert len(files) == 12
for p in files:
    shutil.copyfile(p, T / p.name)
    f = TTFont(p); f.flavor = 'woff2'; f.save(W / (p.stem + '.woff2'))
    w = TTFont(W / (p.stem + '.woff2')); w.ensureDecompiled()
    assert w.getBestCmap() == f.getBestCmap()
    assert w['hmtx'].metrics == f['hmtx'].metrics
    for tag in ('GSUB', 'GPOS', 'GDEF', 'name', 'OS/2', 'vmtx', 'fpgm', 'prep', 'cvt '):
        assert w.getTableData(tag) == f.getTableData(tag), (p.name, tag)
    for n in f.getGlyphOrder():
        a = f['glyf'][n]; b = w['glyf'][n]
        assert a.numberOfContours == b.numberOfContours
        if a.numberOfContours > 0:
            assert list(a.coordinates) == list(b.coordinates)
            assert list(a.endPtsOfContours) == list(b.endPtsOfContours)
    family = 'Friday Mono Plain' if 'Plain' in p.stem else 'Friday Mono'
    weight = 700 if 'Bold' in p.stem else (500 if 'Medium' in p.stem else 400)
    style = 'italic' if 'Italic' in p.stem else 'normal'
    css.append('@font-face {\n  font-family: "%s";\n  src: url("%s.woff2") format("woff2"), '
               'url("../ttf/%s") format("truetype");\n  font-weight: %s;\n  font-style: %s;\n'
               '  font-display: swap;\n}\n' % (family, p.stem, p.name, weight, style))
(W / 'friday-mono.css').write_text('/* Friday Mono v48 — SIL OFL 1.1; see ../OFL.txt */\n' + '\n'.join(css))
(D / 'font-manifest.json').write_text(json.dumps(
    [{'file': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in files],
    indent=2) + '\n')

shutil.copyfile(R / 'RELEASE-v48.md', D / 'README.md')
report = (R / 'review-v47/REPORT.md').read_text()
(D / 'QUALITY-REPORT.md').write_text(
    '# Friday Mono v48 品質調査\n\n'
    'v48 は v47（旧名 Inori Mono）の名称変更版です。輪郭・字幅・ヒント・OpenType 機能は '
    'v47 とバイト単位で同一であることを `rename_v48.py` が確認しています。\n'
    'そのため以下は v47 の調査をそのまま収録しています（ファイル名・書体名は旧名のまま）。'
    '機械検査の生データは `audit/v47/` にあります。\n\n'
    'v47 の Windows（WPF）実機確認：12 本すべて読み込み・描画に成功。'
    'Regular 12/16/20px で仮名・漢字の上端の残差は最大 1px（濁点付きの字が設計上 0.6〜0.9px 高いぶん）。'
    'GDI と個別エディタは未検証。\n\n---\n\n' + report)
shutil.copyfile(R / 'windows-smoke-test.ps1', D / 'windows-smoke-test.ps1')
shutil.copyfile(R / 'requirements-v47.txt', D / 'build-environment.txt')
for name in ['release-audit.json', 'encoding-audit.json', 'coretext-audit.json',
             'browser-audit.json', 'raster-audit.json']:
    shutil.copyfile(R / 'review-v47' / name, A / name)
sources = []
for p in sorted((R.parent / 'Source/Iosevka').glob('IosevkaCustom*.ttf')):
    sources.append({'source': str(p.relative_to(R.parent)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
for p in [R.parent / 'Source/noto-cjk/NotoSansCJKjp-VF.ttf', R / 'drawings/vector-masters.json',
          R / 'drawings/approved-hand-outlines.json']:
    sources.append({'source': str(p.relative_to(R.parent)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
(D / 'source-manifest.json').write_text(json.dumps(sources, indent=2) + '\n')

files = sorted(p for p in D.rglob('*') if p.is_file() and p.name != 'SHA256SUMS.txt')
for p in files:
    assert p.suffix in {'.ttf', '.woff2', '.css', '.txt', '.md', '.json', '.ps1'}, p
    assert p.name != '.DS_Store' and 'SF' not in p.name and 'Hiragino' not in p.name, p
(D / 'SHA256SUMS.txt').write_text(''.join(
    hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.relative_to(D).as_posix() + '\n' for p in files))
archive = R / 'FridayMono-v48.zip'
with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for p in sorted(D.rglob('*')):
        if p.is_file():
            z.write(p, Path('FridayMono-v48') / p.relative_to(D))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert sum(n.endswith('.ttf') for n in z.namelist()) == 12
    assert sum(n.endswith('.woff2') for n in z.namelist()) == 12
    for n in z.namelist():
        assert not n.startswith('/') and '..' not in Path(n).parts
(R / 'FridayMono-v48.zip.sha256').write_text(
    hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')
print('Sealed', archive.name, archive.stat().st_size, 'bytes; WOFF2 roundtrip, ZIP CRC and counts verified')
