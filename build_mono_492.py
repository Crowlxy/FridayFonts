"""Apply the accepted Windows Terminal line metrics to all 4.91 faces.

Run build_mono_49.py first if the local 4.91 inputs are missing.
"""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

import brotli
from fontTools.ttLib import TTFont
from build_underline_trial import layout

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'dist-mono-4.91'
OUT = ROOT / 'dist-mono-4.92'
compress = brotli.compress


def web_compress(data, **kwargs):
    kwargs['quality'] = 6
    return compress(data, **kwargs)


brotli.compress = web_compress


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_delta(original, current):
    # Normalize exactly the allowed fields, then compare every binary table.
    original['hhea'].descent = current['hhea'].descent
    original['OS/2'].sTypoDescender = current['OS/2'].sTypoDescender
    original['head'].fontRevision = current['head'].fontRevision
    original['head'].checkSumAdjustment = current['head'].checkSumAdjustment
    for tag in original.keys():
        if tag not in ('GlyphOrder', 'name'):
            assert original.getTableData(tag) == current.getTableData(tag), tag
    # No family/style/name changes; only version, unique ID and description.
    old_names = {(r.nameID, r.platformID, r.platEncID, r.langID): r.toUnicode()
                 for r in original['name'].names if r.nameID not in (3, 5, 10)}
    new_names = {(r.nameID, r.platformID, r.platEncID, r.langID): r.toUnicode()
                 for r in current['name'].names if r.nameID not in (3, 5, 10)}
    assert old_names == new_names


def main():
    for folder in ('ttf', 'web', 'reports', 'reports/inherited-4.91', 'licenses'):
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    old_rows = json.loads((SOURCE / 'font-manifest.json').read_text())
    assert len(old_rows) == 18
    rows, results = [], []
    for old in old_rows:
        source = SOURCE / old['ttf']
        assert sha(source) == old['sha256'], source
        f = TTFont(source, recalcTimestamp=False)
        assert (f['hhea'].descent, f['OS/2'].sTypoDescender) == (-120, -120)
        assert f['OS/2'].fsSelection & 128
        f['hhea'].descent = f['OS/2'].sTypoDescender = -400
        f['head'].fontRevision = 4.92
        ps = f['name'].getDebugName(6)
        labels = {3: 'FridayProject;4.920;' + ps, 5: 'Version 4.920',
                  10: 'Friday Mono 4.92: Windows Terminal double underline line metrics fix. Glyph data unchanged from 4.91.'}
        for rec in f['name'].names:
            if rec.nameID in labels:
                rec.string = labels[rec.nameID].encode(rec.getEncoding(), errors='replace')
        for nid, val in labels.items():
            f['name'].setName(val, nid, 3, 1, 0x409)
        path, web = OUT / old['ttf'], OUT / old['woff2']
        f.save(path)
        f.flavor = 'woff2'
        f.save(web)
        current, original, w = (TTFont(p, recalcTimestamp=False) for p in (path, source, web))
        check_delta(original, current)
        for tag in current.keys():
            if tag not in ('GlyphOrder', 'head', 'glyf', 'loca'):
                assert current.getTableData(tag) == w.getTableData(tag), (path.name, tag)
        assert current.getGlyphOrder() == w.getGlyphOrder()
        for name in current.getGlyphOrder():
            assert current['glyf'][name].getCoordinates(current['glyf']) == w['glyf'][name].getCoordinates(w['glyf'])
            assert getattr(current['glyf'][name], 'program', None) == getattr(w['glyf'][name], 'program', None)
        predictions = [layout(current, p, dpi) for dpi in (96, 120, 144, 192) for p in range(8, 25)]
        assert all(r['two_separate_lines'] for r in predictions), path.name
        row = dict(old, source=str(source.relative_to(ROOT.parent)), source_sha256=sha(source),
                   sha256=sha(path), woff2_sha256=sha(web))
        rows.append(row)
        results.append(dict(file=path.name, exact_delta_verified=True, unchanged_glyph_layout_hint_tables=True,
                            ttf_woff2_parity=True, underline_predictions=predictions))
        print(path.name, 'PASS', flush=True)
        for font in (f, current, original, w):
            font.close()
    (OUT / 'font-manifest.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    (OUT / 'reports/validation.json').write_text(json.dumps(dict(
        changes=['hhea.descent: -120 -> -400', 'OS/2.sTypoDescender: -120 -> -400',
                 'head.fontRevision and name IDs 3/5/10; checksum recalculated'],
        unchanged='Every other TTF table/field is byte identical to the corresponding 4.91 input.',
        windows_evidence='User confirmed two lines and acceptable line spacing in Windows Terminal with the Regular trial. No separate native Windows test of all 18 release faces.',
        model_scope='Current AtlasEngine formula; default cell height and USE_TYPO_METRICS; 8–24pt at 96/120/144/192 DPI.',
        terminal_source='https://github.com/microsoft/terminal/blob/main/src/renderer/atlas/AtlasEngine.api.cpp',
        results=results), ensure_ascii=False, indent=2) + '\n')
    shutil.copy2(SOURCE / 'web/friday-mono.css', OUT / 'web/friday-mono.css')
    for name in ('validation.json', 'italic-render-audit.json', 'coverage-comparison.json'):
        shutil.copy2(SOURCE / 'reports' / name, OUT / 'reports/inherited-4.91' / name)
    for p in (SOURCE / 'licenses').glob('*.txt'):
        shutil.copy2(p, OUT / 'licenses' / p.name)
    shutil.copy2(ROOT / 'OFL.txt', OUT / 'OFL.txt')
    for name in ('build_mono_492.py', 'build_underline_trial.py'):
        shutil.copy2(ROOT / name, OUT / 'reports' / name)
    readme = '''# Friday Mono 4.92 / 2026-10-04

Windows Terminalで二重下線が一重に見えるバグを修正しました。
変換で選択中の文節とANSI二重下線に影響していた行の下側の余白を120から400 unitsへ拡大。
行高は1.00emから1.28emになります。Regularテスト版でWindows上の二重線と行間をユーザー確認済みです。

3ファミリ（Friday Mono / Friday Mono JP / Friday Mono Plain JP）、各Regular / Medium / Boldと各Italic。
計18 TTF、18 WOFF2。既存の正式書体名を維持しています。

4.91からの変更はhhea.descent、OS/2.sTypoDescender、版情報・説明とチェックサムのみです。
字形・文字幅・ヒント・文字収録・文字置換・位置調整・下線位置と太さは4.91と同一です。
保存後に変更対象以外の全テーブル・フィールドの完全一致を18書体で確認し、TTF/WOFF2も照合しました。
Terminalの計算式では全18書体、8–24pt・96/120/144/192 DPIの計1,224条件で二重線が分離します。
これは計算による予測です。全18書体をWindows実アプリで個別に再検証したという意味ではありません。
セル高のカスタム設定や別レンダラーはこの計算の対象外です。

## インストール

1. 使用するファミリのttf/内の書体をWindowsにインストール（4.91の置き換え）。
2. Windows Terminalを再起動し、Friday MonoまたはFriday Mono JPを選択します。
3. PowerShellで二重下線を確認します。

```powershell
$e = [char]27; Write-Host "${e}[4:2mABC クローン${e}[0m"
```

テスト版の「UL Test」とは別名です。日本語なしのFriday Monoは日本語を別フォントで表示します。
日本語入りはFriday Mono JP（斜線入り0）またはFriday Mono Plain JP（斜線なし0）です。

## 検証記録

reports/validation.jsonは今回の4.92の検査です。
reports/inherited-4.91/は4.91当時の検査記録で、今回のWindows全書体の確認結果ではありません。
文字収録・ゼロ切り替え・RC3修正内容は4.91から継承しています。

再ビルド：4.91の入力をbuild_mono_49.pyで用意し、build_mono_492.pyを実行します。
workspaceルートから `InoriMono-v3-build/.venv/bin/python FridayFonts/build_mono_492.py`。
'''
    (OUT / 'README.md').write_text(readme)
    files = sorted(p for p in OUT.rglob('*') if p.is_file() and p.name != 'SHA256SUMS.txt')
    (OUT / 'SHA256SUMS.txt').write_text(''.join(sha(p) + '  ' + p.relative_to(OUT).as_posix() + '\n' for p in files))
    archive = ROOT / 'FridayMono-4.92.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(OUT.rglob('*')):
            if p.is_file():
                z.write(p, Path('FridayMono-4.92') / p.relative_to(OUT))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert sum(n.endswith('.ttf') for n in z.namelist()) == 18
        assert sum(n.endswith('.woff2') for n in z.namelist()) == 18
        for p in OUT.rglob('*'):
            if p.is_file():
                assert hashlib.sha256(z.read('FridayMono-4.92/' + p.relative_to(OUT).as_posix())).hexdigest() == sha(p)
    archive.with_suffix('.zip.sha256').write_text(sha(archive) + '  ' + archive.name + '\n')
    print(archive, round(archive.stat().st_size / 1024**2, 1), 'MiB; 18 faces / 1224 model cases / ZIP hashes PASS')


if __name__ == '__main__':
    main()
