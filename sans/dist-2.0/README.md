# Friday Sans — version 2.0

ファミリー名は **Friday Sans**。2.0はバージョン番号であり、ファミリー名には含めない。Regular / Medium / Boldの静的3ウェイト。内部バージョンはVersion 2.000、fontRevisionは2.0。

## 変更

日本語と英数字が一書体として自然に読めることを目標に、Inter由来の英数字を再調整した。大文字・小文字の高さの比、和文に対する線の太さ、平均小文字送り幅、ベースラインを、ヒラギノSans W3 / W4 / W6から測った比率に合わせた。日本語側は既存Friday Sans 1.1の字形・字幅・縦書き情報を維持。英数字のカーニング・マーク位置も寸法変更に合わせて処理した。

先行する一体感試作でも残っていた、和文ヒントによる文字ごとの濃さの変化を取り除くため、日本語側グリフのTrueType命令を除去した。英数字のヒントと数字の上下位置補正は保持。フォント全体のfpgm / prep / cvtは英数字のため残している。描画エンジン側の補正まで無効にする指定ではない。

ヒラギノは数値と比較画像のみ参照。配布TTF / WOFF2へヒラギノやSF Proの字形・フォントデータをコピーしていない。素材はInterと既存Friday SansのNoto由来和文・独自仮名。

## 使用

- ttf/：デスクトップ用3本。既存のFriday Sans 1.0 / 1.1とは同じファミリー・PostScript名なので、インストールする場合は旧版を置き換える。同時インストールで比較しない。
- web/：Web用WOFF2。font-familyはFriday Sans、font-weightは400 / 500 / 700として設定する。
- preview.html：フォント埋め込み比較。インストール不要。ZIPを展開して開く。旧1.0 / 1.1 / 2.0を同じOS・ブラウザ・サイズで比較できる。
- proof-*.png / kana-grid-14px.png：FreeTypeによる比較画像。ブラウザやWindows実機とは描画条件が異なる。

旧WindowsのRIBBI制約のため、Mediumのlegacy name ID 1はFriday Sans Medium。typographic family（name ID 16）は全3本Friday Sans。この命名は1.1と同じ。2.0を名前へ付けていない。

## 確認できたことと残る確認

全3本で13,806個の和文グリフ（OpenTypeの非符号化代替も含む）を12 / 14 / 16 / 18 / 20pxで描画し、同じ輪郭を明示的にヒント無効で描画した結果と、画素・位置が一致した。合計207,090ケース。輪郭・字幅・OpenTypeレイアウト・行メトリクスは先行する一体感試作と一致し、英数字の命令も維持。数字の上下位置は9〜24pxの11サイズで検査した。CoreTextでは日本語・英数字・結合文字の試験文がフォールバックせず、欠落文字もなく、AVのカーニングが有効であることを確認した。

このFreeType設定では、仮名・漢字のヒントによるインク量変化は0になった。これはヒント起因の変化を除いた確認であり、文字間の見かけの太さや読みやすさが完全に揃った証明ではない。例えば複雑な漢字は本来インクが多く、別の字の総インク量と揃えることは目標にしていない。

**Windows実機での仕上がりは未検証。** 同じアプリ、画面倍率、12〜16pxで、濃さ・輪郭の鮮明さ・上下位置・英数字との一体感を確認する必要がある。和文の強いスナップを除いた結果、低解像度の環境では輪郭が柔らかく見える可能性もある。比較HTMLは生成とJavaScript構文の検査まで行い、今回のブラウザ動作確認は行っていない。

hhea / Typoは1.1と同じ1130 / −370 / 0。拡大した英数字の重ねアクセントを切らないよう、Win上端はRegular 1157 / Medium 1181 / Bold 1200へ拡張した。古いGDIでは行高が変わる可能性がある。縦書き専用のくの字点2字のクリップ範囲の制限は従来と同じ。

## 再生成

プロジェクトルートから、先行試作のfonts-hintedを入力に使用する：

```
InoriMono-v3-build/.venv/bin/python comparisons/friday-sans-2.0/build_release.py
InoriMono-v3-build/.venv/bin/python comparisons/friday-sans-2.0/verify_release.py
swift -module-cache-path /private/tmp/friday-sans-2-swift-cache comparisons/friday-sans-2.0/verify_coretext.swift FridayFonts/sans/dist-2.0
InoriMono-v3-build/.venv/bin/python comparisons/friday-sans-2.0/make_preview.py
InoriMono-v3-build/.venv/bin/python comparisons/friday-sans-2.0/package_release.py
```

design-measurements.jsonに設計数値、validation.jsonに描画検証、font-manifest.jsonに入力・出力ハッシュを収録。OFL.txtとlicenses/に素材の著作権表示・ライセンスを同梱。
