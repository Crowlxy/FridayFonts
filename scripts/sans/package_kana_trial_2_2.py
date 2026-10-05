"""Package the checked kana trial with matched Windows comparison fonts."""
import hashlib,json,re,shutil,subprocess,zipfile
from pathlib import Path
from fontTools.ttLib import TTFont
from kana_hint_common import ROOT
from build_kana_trial_2_2 import OUT

HERE=Path(__file__).resolve().parent
REL=HERE.parents[1]/'releases/archive'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    v=json.loads((OUT/'validation.json').read_text());manifest=json.loads((OUT/'font-manifest.json').read_text())
    assert sum(f['render_cases'] for f in v['faces'])==704424
    assert all(f['raster_errors']==0 for f in v['faces'])
    assert all(f['new_glyph_program_errors']==0 for f in v['strict_new_kana_programs'])
    assert all(f['lost_alpha128_counters']==0 for f in v['fractional_guards'])
    assert all(x['counters'][1]>=x['counters'][0] for f in v['faces'] for x in f['composites'])
    assert 'CORETEXT KANA CHECKS PASSED' in (OUT/'coretext-validation.txt').read_text()
    for row in manifest:assert sha(OUT/f"ttf/FridaySansKanaTrial-{row['style']}.ttf")==row['ttf_sha256']
    original=json.loads((REL/'sans-2.1/font-manifest.json').read_text())
    for row in original:
        style=row['style']
        assert sha(REL/f'sans-2.1/ttf/FridaySans-{style}.ttf')==row['ttf_sha256']
        assert sha(REL/f'sans-grid-trial-2.1/ttf/FridaySans-{style}.ttf')==row['trial_sha256']
        for folder,title in [('dist-2.1','normal-2.1'),('grid-trial-2.1','kanji-trial-2.1')]:
            dest=OUT/f'reference-fonts/{title}';dest.mkdir(parents=True,exist_ok=True)
            prefix='FridaySansGridTrial' if folder=='grid-trial-2.1' else 'FridaySans'
            shutil.copy2(HERE/f'{folder}/ttf/FridaySans-{style}.ttf',dest/f'{prefix}-{style}.ttf')
    for row in json.loads((REL/'sans-2.0/font-manifest.json').read_text()):
        assert sha(REL/f"sans-2.0/ttf/FridaySans-{row['style']}.ttf")==row['ttf_sha256']
    regular=[m for m in v['matched_metrics'] if m['style']=='Regular' and m['ppem'] in [12,14,16] and m['group'] in ['hiragana','katakana']]
    table='\n'.join(f"| {m['ppem']} | {'ひらがな' if m['group']=='hiragana' else 'カタカナ'} | {m['low_alpha_ink_median_percent'][0]:.1f}% | {m['low_alpha_ink_median_percent'][1]:.1f}% | {m['ink_change_p10_median_p90'][1]:+.2f}% |" for m in regular)
    README='''# Friday Sans Kana Trial 2.2 — Windows確認用

かな・カタカナの小サイズ表示を調整した別ファミリーの試作です。ファミリー名は **Friday Sans Kana Trial**、内部バージョンは2.201。Regular / Medium / Boldの3ウェイトです。既存の漢字ヒント試作を含みます。Windowsでの見え方は未確認なので、実機比較後に採否を決めます。

## 変更

- 字形の輪郭と既存の文字幅・行送りを保持し、11〜18 device ppemのかな・カタカナ・付随記号・縦書き用字形に補正を追加しました。
- 全体の縦位置を最大1/4画素、輪郭各点の縦移動を最大1/2画素に制限しています。横方向の輪郭は動かしていません。
- FreeTypeでインク量変化が約±5%を超える候補、α128以上で見えていた白い穴が消える候補を除外しました。端数サイズでも同じ検査をしています。条件を満たせないサイズでは元の描画を保持します。これは可読性そのものの保証ではありません。
- 「ぱ・ピ」などの通常の半濁音は各字の補正対象です。結合用半濁点U+309Aと、2.1で追加した非標準の合成半濁点14組は、縮小時の丸を守るため元の描画を保持します。合成用には同一輪郭の非公開コンポーネント14個を追加しました。収録文字は増えていません。
- 半角カタカナは今回の補正対象外です。英数字・漢字の描画は漢字ヒント試作2.1と同じです。新しい「𠮷」には漢字ヒントがありません。

## Windows実機での確認手順

1. ZIPを展開し、`windows-check.html`をEdge / Chromeで開いてください。HTML単独でも動きます。9フォント内蔵で、インストール不要です。
2. ブラウザズーム100%、Windows表示倍率100%、Regularの12・14・16pxから比較してください。中央と右の差が今回のかな調整です。左は日本語を補正していない通常2.1です。
3. 「ひらがな一覧」「カタカナ一覧」「小書き・濁点・結合文字」を切り替え、明るい背景と暗い背景で見てください。特に「る・ろ・ゃ」「き・さ・ふ」「シ・ツ・ソ・ン」「リ・ル・レ・ロ」「ぱ・ピ」の線・丸・濃さを確認してください。
4. Medium / Boldも確認し、普段の表示倍率125%・150%でも比較してください。補正範囲はCSS pxではなくdevice ppemなので、高DPIでは差が出ない条件があります。
5. アプリで試す場合は`ttf/`の3ファイルをインストールし、**Friday Sans Kana Trial**を選択してください。旧式アプリでMediumが出ない場合は、別のファミリー **Friday Sans Kana Trial Medium** を選びます。今回のファミリーは通常2.1と共存できます。
6. 通常版・漢字試作のTTFも`reference-fonts/`に含めました。通常版のFriday Sansは2.0以前と同名なので、旧版と比較する際はバージョンを確認してください。
7. ページ下部でWindowsのバージョン・表示倍率・気になった文字を記入し、条件ごとにJSONで保存できます。実際に使うアプリでは、アプリ名・文字サイズ・倍率・背景・気になる文字も記録してください。

## ローカル診断

以下はFreeType 2.14.3 / interpreter 40、Regularでの、薄い画素（α128未満）に配られたインク量の割合の中央値です。各文字を同じ条件で比較しています。薄い線の分散を見る指標で、可読性の得点やWindows / ClearTypeの再現ではありません。

| device ppem | 群 | 漢字のみ試作＝かな補正前 | 今回 | インク量変化中央値 |
|---|---|---:|---:|---:|
''' + table + '''

## 検証

- 3ウェイト・16,772グリフを9 / 10 / 11 / 12 / 13 / 14 / 15 / 16 / 17 / 18 / 19 / 20 / 24 / 32ppemで検査。**704,424ケースで通常描画エラー・輪郭のあるグリフの全消失0**。
- かな・付随字形406個 × 80の整数・端数条件 × 3ウェイト、計97,440ケースでインク量変化は約±5%以内、α128での白い穴の減少0。
- 新しいかな命令と合成半濁点をFreeTypeの厳格な命令実行で検査。追加命令の参照エラー0。interpreter 35でも全かな・合成字形を検査し、描画エラー0、縦移動最大1/2画素。
- 元の16,758グリフの輪郭・文字幅・行送り、cmap / GSUB / GPOS / GDEF / 共通ヒントを保持。対象外の文字、および補正範囲外の検査サイズの画素一致を確認。
- 合成半濁点14組・濁音・「𠮷」/異体字セレクタ・英字カーニング・等幅数字をHarfBuzz / CoreTextで確認。
- TTF / WOFF2の主要テーブル一致、macOS Chrome 154 / DPR 2で9フォント読込、ウェイト・背景・文章の切替を確認。Windows実機は未確認。

## 継続課題

小さい漢字の密度、半角カタカナ、アプリ間の違いはWindows実機で確認が必要です。2.1から残っている「〱・〲」のWinメトリクス外への張り出し、和文palt/halt未実装などは今回変更していません。既存共通ヒントには、FreeTypeの厳格実行でサイズ切替時に参照エラー134が出るケースがあります。通常2.1にも同じ現象があり、通常描画の検査ではエラーは出ていません。今回追加したかな命令は別途厳格検査済みです。

`proof-*.png`は共通条件のFreeType比較画像です。Windowsでの採否は、実際の画面表示で決めてください。`validation.json`、`font-manifest.json`、`hint-settings.json`、`sources.json`に検査・入力・設定を記録しました。

## 技術資料

- [Microsoft TrueType命令仕様](https://learn.microsoft.com/en-us/typography/opentype/spec/tt_instructions)
- [Microsoft ClearTypeでのTrueType命令](https://learn.microsoft.com/en-us/typography/cleartype/truetypecleartype)
- [FreeTypeのTrueTypeドライバー](https://freetype.org/freetype2/docs/reference/ft2-tt_driver.html)

ヒラギノのフォントデータ・字形は生成フォントにコピーしていません。Inter / NotoのOFLを`licenses/`に含めています。
'''
    (OUT/'README.md').write_text(README)
    (OUT/'sample-text.txt').write_text('''設定 Settings　表示 Display　保存 Save　キャンセル Cancel
読みやすい文字で、毎日の作業を快適に。Windows 11 の表示設定
あいうえお かきくけこ さしすせそ たちつてと なにぬねの
はひふへほ まみむめも やゆよ らりるれろ わをん
がぎぐげご ざじずぜぞ だぢづでど ばびぶべぼ ぱぴぷぺぽ
ぁぃぅぇぉ っゃゅょゎ ゕゖ きゃきゅきょ しゃしゅしょ
アイウエオ カキクケコ サシスセソ タチツテト ナニヌネノ
ハヒフヘホ マミムメモ ヤユヨ ラリルレロ ワヲン
ガギグゲゴ ザジズゼゾ ダヂヅデド バビブベボ パピプペポ
ァィゥェォ ッャュョヮ ヵヶ キャキュキョ シャシュショ
きさふとや ぎざぷどゃ るろりれ ぬねめ
シツソン リルレロ ユコニ フラワー
カ゚キク か゚きく き゚く゚け゚こ゚ セ゚ツ゚ト゚ㇷ゚
ㇰㇱㇲㇳㇴㇵㇶㇷㇸㇹㇺㇻㇼㇽㇾㇿ
価格 ¥12,345（税込） / 20% OFF / 0123456789
日田目国語書機 警響議識曜覧鬱鷹
𠮷野家 𠮷田 髙橋 﨑山 / （入力）「情報」［設定］
ｱｲｳｴｵ ｶﾀｶﾅ ｶﾞﾊﾟ
''',encoding='utf-8-sig')
    (OUT/'web/friday-sans.css').write_text('\n'.join(f'@font-face{{font-family:"Friday Sans Kana Trial";src:url("FridaySansKanaTrial-{s}.woff2") format("woff2");font-weight:{w};font-style:normal;}}' for s,w in [('Regular',400),('Medium',500),('Bold',700)])+'\n.friday-numeric{font-variant-numeric:tabular-nums;}\n')
    scripts=['kana_hint_common.py','explore_kana_hint.py','optimize_kana_hint.py','refine_kana_hint.py','filter_unsafe_kana_donors.py','protect_combining_ring.py','build_kana_trial_2_2.py','verify_kana_trial_2_2.py','preview_kana_trial_2_2.py','kana-preview-template.html','package_kana_trial_2_2.py','verify_kana_coretext.swift']
    inputs=[HERE/s for s in scripts]
    inputs += [ROOT/f'comparisons/unified-sans-trial/fonts-hinted/UnitySansTrial-{s}.ttf' for s in ['Regular','Medium','Bold']]
    inputs += [REL/f'sans-grid-trial-2.1/ttf/FridaySans-{s}.ttf' for s in ['Regular','Medium','Bold']]
    sources={'inputs':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in inputs],
             'browser':{'platform':'macOS','browser':'Chrome 154','DPR':2,'all_nine_webfonts_loaded':True,'weight_dark_and_preset_controls_checked':True},'windows_verified':False}
    (OUT/'sources.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
    js=re.search(r'<script>(.*?)</script>',(OUT/'windows-check.html').read_text(),re.S).group(1)
    jp=Path('/private/tmp/friday-kana-pack-check.js');jp.write_text(js);subprocess.run(['node','--check',str(jp)],check=True)
    for p in (OUT/'ttf').glob('*.ttf'):
        f=TTFont(p);assert len(f.getGlyphOrder())==16772 and 0x20bb7 in f.getBestCmap();f.close()
    files=[p for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.txt']
    sums=OUT/'SHA256SUMS.txt';sums.write_text(''.join(sha(p)+'  '+str(p.relative_to(OUT))+'\n' for p in files));files.append(sums)
    name='FridaySans-KanaTrial-2.2-WindowsCheck';dest=HERE/(name+'.zip')
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.write(p,name+'/'+str(p.relative_to(OUT)))
    with zipfile.ZipFile(dest) as z:
        assert z.testzip() is None
        for p in files:assert hashlib.sha256(z.read(name+'/'+str(p.relative_to(OUT)))).hexdigest()==sha(p)
    dest.with_suffix('.zip.sha256').write_text(sha(dest)+'  '+dest.name+'\n')
    print('Windows comparison kit packaged and verified:',dest.stat().st_size,'bytes',flush=True)

if __name__=='__main__':main()
