"""Build isolated Regular fonts for Windows Terminal double-underline checks."""
from pathlib import Path
import hashlib
import json
import math
import shutil
import zipfile

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'FridayFonts/dist-mono-4.91'
OUT = ROOT / 'comparisons/mono-double-underline-2026-10-04'
URL = 'https://github.com/microsoft/terminal/blob/main/src/renderer/atlas/AtlasEngine.api.cpp'


def rounded(value):
    # C++ roundf: positive ties round away from zero, unlike Python round.
    return math.floor(value + 0.5)


def layout(font, points, dpi):
    upm = font['head'].unitsPerEm
    scale = points / 72 * dpi / upm
    ascent = font['OS/2'].sTypoAscender * scale
    descent = -font['OS/2'].sTypoDescender * scale
    gap = font['OS/2'].sTypoLineGap * scale
    advance = ascent + descent + gap
    cell = rounded(advance)
    baseline = rounded(ascent + (gap + cell - advance) / 2)
    underline = rounded(baseline - font['post'].underlinePosition * scale)
    thickness = max(1, rounded(font['post'].underlineThickness * scale))
    double_thickness = max(1, rounded(font['post'].underlineThickness * scale / 2))
    bottom = underline + thickness - double_thickness
    top = max(rounded((baseline + bottom - double_thickness) / 2), baseline + double_thickness)
    minimum_gap = max(1, rounded(1.2 / 72 * dpi))
    bottom = min(max(bottom, top + minimum_gap + double_thickness), cell - double_thickness)
    return dict(points=points, dpi=dpi, cell_height=cell, baseline=baseline,
                top=top, bottom=bottom, thickness=double_thickness,
                visible_gap=bottom - top - double_thickness,
                two_separate_lines=bottom > top + double_thickness)


def main():
    (OUT / 'ttf').mkdir(parents=True, exist_ok=True)
    report = dict(source_release='4.91', terminal_source=URL,
                  model_scope='AtlasEngine default cell height; DirectWrite USE_TYPO_METRICS assumed. Not a Windows render test.',
                  change='hhea.descent and OS/2.sTypoDescender: -120 -> -400; line height 1.00em -> 1.28em; distinct trial family names.',
                  faces=[])
    for stem, family in [('FridayMono', 'Friday Mono UL Test'),
                         ('FridayMonoJP', 'Friday Mono JP UL Test'),
                         ('FridayMonoPlainJP', 'Friday Mono Plain JP UL Test')]:
        src = SOURCE / 'ttf' / (stem + '-Regular.ttf')
        font = TTFont(src, recalcTimestamp=False)
        assert font['OS/2'].fsSelection & 128, 'model requires USE_TYPO_METRICS'
        old = [layout(font, p, dpi) for dpi in (96, 120, 144, 192) for p in range(8, 25)]
        font['hhea'].descent = -400
        font['OS/2'].sTypoDescender = -400
        ps = family.replace(' ', '') + '-Regular'
        labels = {1: family, 2: 'Regular', 3: 'FridayProject;4.911-UL-Test;' + ps,
                  4: family + ' Regular', 5: 'Version 4.911; Underline Test',
                  6: ps, 16: family, 17: 'Regular',
                  10: 'Windows Terminal double underline trial. Line height 1.28em. Windows verification pending.'}
        font['head'].fontRevision = 4.911
        for rec in font['name'].names:
            if rec.nameID in labels:
                rec.string = labels[rec.nameID].encode(rec.getEncoding(), errors='replace')
        for nid, value in labels.items():
            font['name'].setName(value, nid, 3, 1, 0x409)
        dest = OUT / 'ttf' / (ps + '.ttf')
        font.save(dest)
        new = TTFont(dest, recalcTimestamp=False)
        original = TTFont(src, recalcTimestamp=False)
        unchanged = []
        for tag in original.keys():
            if tag in ('GlyphOrder', 'head', 'hhea', 'OS/2', 'name'):
                continue
            assert original.getTableData(tag) == new.getTableData(tag), (stem, tag)
            unchanged.append(tag)
        assert original['hmtx'].metrics == new['hmtx'].metrics
        current = [layout(new, p, dpi) for dpi in (96, 120, 144, 192) for p in range(8, 25)]
        assert all(row['two_separate_lines'] for row in current), current
        report['faces'].append(dict(family=family, file=dest.name,
                                    source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
                                    sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
                                    unchanged_tables=unchanged, before=old, after=current))
    (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    readme = '''# Friday Mono 二重下線テスト版

Windows Terminalで二重下線が一重に見える問題の比較用です。正式リリースではありません。

1. ttf/FridayMonoULTest-Regular.ttfをWindowsでインストールします。
2. Terminalのフォントを「Friday Mono UL Test」に変更します（Regular）。
3. PowerShellで次を実行し、二重線を確認します。

```powershell
$e = [char]27; Write-Host "${e}[4:2mABC クローン${e}[0m"
```

日本語入りを比較する場合はFridayMonoJPULTest-Regular.ttfと「Friday Mono JP UL Test」を使用します。
Plain JP版も同梱しています。既存フォントと別名なので併存できます。

変更：行の下側の余白を120から400 unitsに拡大。行高は1.00emから1.28emになるため、画面内の行数は減ります。
輪郭、文字幅、ヒント、文字収録、置換・位置調整、下線位置と太さのテーブルは元4.91と同一です。
変換中のIME文節選択でも二重線が出るか確認してください。

検証：保存後に変更対象以外の全テーブルを元データと照合しました。
Terminalの現行AtlasEngineの計算式では、8–24pt・96/120/144/192 DPIの68条件で2本が分離します。
これは計算による予測です。実際のWindows/DirectWrite描画の確認は未実施です。
セル高のカスタム設定や別のレンダラーはこの計算の対象外です。
出典：https://github.com/microsoft/terminal/blob/main/src/renderer/atlas/AtlasEngine.api.cpp
'''
    (OUT / 'README.md').write_text(readme)
    (OUT / 'licenses').mkdir(exist_ok=True)
    for p in (SOURCE / 'licenses').glob('*'):
        shutil.copy2(p, OUT / 'licenses' / p.name)
    shutil.copy2(ROOT / 'FridayFonts/OFL.txt', OUT / 'licenses/Friday-OFL.txt')
    archive = OUT / 'FridayMono-Underline-Test.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.rglob('*')):
            if p.is_file() and p != archive:
                z.write(p, p.relative_to(OUT))
    print(json.dumps(dict(zip=str(archive), families=[f['family'] for f in report['faces']],
                          old_12pt_96dpi=report['faces'][0]['before'][4],
                          new_12pt_96dpi=report['faces'][0]['after'][4],
                          predicted_separate_conditions=68), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
