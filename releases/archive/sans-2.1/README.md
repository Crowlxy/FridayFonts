# Friday Sans 2.1

Regular / Medium / Boldの3ウェイト。ファミリー名はFriday Sans、内部バージョンはVersion 2.100。

## 修正内容

1. 仮名＋結合半濁点の合成14組を追加。`か゚き゚く゚け゚こ゚ / カ゚キ゚ク゚ケ゚コ゚セ゚ツ゚ト゚ㇷ゚`を1つの合成グリフとして描く。既存の仮名の体を使い、半濁点をNotoの合成位置に合わせて配置する。手描きの「き」も維持。
2. 合成しない結合濁点・半濁点にはOpenTypeのmark-to-base配置を追加。仮名193字の添付位置を登録し、GDEFの基底字・マーク分類も設定した。通常の「が・ぱ」、英字のアクセント・カーニングは回帰検査で維持を確認。
3. 「𠮷」（U+20BB7）を追加。Notoの日本語字形を各ウェイトの漢字と同じ軸値・縮尺・上下配置で生成し、全角1000 unitsで収録。U+20BB7 U+E0100の標準異体字シーケンスも追加。その他の未収録文字を全て追加した版ではない。

元の16,743グリフの輪郭・字幅・縦メトリクス・グリフ命令は保持。追加は合成14字形＋漢字1字形の計15。全16,758グリフ、Unicode収録15,233符号位置。

## 漢字ヒントの試作

`../grid-trial-2.1/`に別ファミリー **Friday Sans Grid Trial** を作成。2.1の字形・配置修正を含み、既存漢字のChlorophytum命令だけを11〜18 device ppemに限定して適用する。仮名には戻さない。範囲外と仮名・英数字の画素は全サイズで2.1と一致することを検査した。「𠮷」には既存のヒントがないため、試作でも輪郭のみで描画する。

**試作はWindowsでの比較候補であり、Windowsの仕上がりを確認済みの版ではない。** macOSの高DPIブラウザではdevice ppemが大きくなるため、2.1との差が出ない場合がある。

FreeType 2.14.3のRegular漢字サンプルで、α128未満の画素に配られるインク量の割合（各字の値の中央値）は次のように変化した。薄い画素への分散を見る診断であり、可読性の得点ではない。

| device ppem | 2.1 | 漢字ヒント試作 | インク量増減中央値 |
|---|---:|---:|---:|
| 12 | 31.8% | 20.1% | +6.3% |
| 14 | 30.1% | 18.8% | +0.7% |
| 16 | 25.4% | 16.5% | +1.7% |

比較画像では漢字の線がまとまる。12pxはインクが増えるため、細かい漢字の密度もWindowsで確認する必要がある。

## 検証

- 2.1・ヒント試作の各3ウェイト、全グリフを9 / 10 / 11 / 12 / 13 / 14 / 16 / 18 / 20 / 24 device ppemで検査。計1,005,480ケースで描画エラー、輪郭のあるグリフの全消失、異常な高さの潰れは0。
- 全元グリフの輪郭・字幅・縦メトリクス・命令一致、行メトリクス維持、フォントテーブル読込・再コンパイル、TTF / WOFF2の輪郭・OpenTypeテーブル一致を確認。
- HarfBuzzで合成14組、前後の文字がある配置、ccmpを無効にした場合のmark配置、通常の濁音・半濁音、アクセント、AV/To、数字、約物を検査。
- macOS CoreTextでも合成14組、前後の文字、𠮷・異体字シーケンス、欠落・フォールバック、カーニングを確認。
- macOS Chrome 153 / DPR 2で比較HTMLを開き、2.0 / 2.1 / ヒント試作の3ウェイト（計9フォント）とローカルヒラギノW3/W4/W6の読込、ウェイト切替、暗い背景、配置を確認。
- Windows実機のDirectWrite / GDI / WPF / WinUIでの表示は未確認。

結果は`validation.json`、入力・出力ハッシュと配置情報は`font-manifest.json`と`sources.json`、ネイティブ描画の確認は`coretext-validation.txt`に記録。

## 使用

- `ttf/`：デスクトップ用。2.0以前と同じファミリー名・PostScript名なので、旧版を置き換えて使う。Mediumは旧式WindowsのRIBBI互換用にlegacy familyがFriday Sans Medium。
- `web/`：Web用WOFF2。400 / 500 / 700を割り当てる。
- `windows-check.html`：全文字フォントを内蔵した単独比較ファイル。WindowsへこのファイルだけコピーしてEdge / Chromeで開ける。インストール不要。ヒラギノはローカル読込に成功した場合のみ表示。
- `shaping-fix.png`：配置・収録修正の前後比較。
- `proof-*.png`：FreeTypeによるヒラギノとのローカル比較。配布ZIPには含めない。

金額・時刻の桁を揃える場合は`font-variant-numeric: tabular-nums`等でtnumを指定する。2.1でも日本語のpalt / haltは未実装。縦書き用のくの字点〱・〲が旧GDIのWinクリップ範囲を超える制限も残っている。文字範囲外の人名・地名は引き続きアプリのフォールバックに依存する。

Windows確認はブラウザズーム100%、画面倍率100% / 125% / 150%、同じ12〜16px、明暗の背景で実施する。ブラウザに加えて実際に使うアプリでも確認する。

## 再生成

プロジェクトルートから：

```sh
InoriMono-v3-build/.venv/bin/python FridayFonts/sans/build_2_1.py
InoriMono-v3-build/.venv/bin/python FridayFonts/sans/verify_2_1.py
swift -module-cache-path /private/tmp/friday-21-swift-cache FridayFonts/sans/verify_2_1_coretext.swift FridayFonts/sans/dist-2.1
InoriMono-v3-build/.venv/bin/python FridayFonts/sans/preview_2_1.py
InoriMono-v3-build/.venv/bin/python FridayFonts/sans/package_2_1.py
```

入力は保存済み2.0、承認済みCJKマスターのpickle、Noto Sans CJK JP、漢字ヒント試作のための既存ヒント付きマスター。ヒラギノの字形・フォントデータは生成フォントへコピーしていない。元2.0の配布物は変更していない。

フォントの利用・再配布条件は同梱`OFL.txt`と`licenses/`を参照。
