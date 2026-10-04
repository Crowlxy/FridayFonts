# Friday Mono 4.9 / 2026-10-04

最新のMono RC3を基準に、JP版と日本語なし版を作成しました。

| ファミリ | 日本語 | 既定の0 | Unicode文字数 | ウエイト |
|---|---|---|---:|---|
| Friday Mono JP | あり | 斜線あり | 19,312 | Regular / Medium / Bold |
| Friday Mono Plain JP | あり | 斜線なし | 19,312 | Regular / Medium / Bold |
| Friday Mono | なし | 斜線あり | 1,088 | Regular / Medium / Bold |

計9 TTFと9 WOFF2。日本語なし版のPlainは作成していません。
ItalicはRC3で修正・検証した元データがないため、この4.9パッケージには含めていません。
旧4.8のItalicを4.9へ名前だけ変えて混ぜてはいません。

## Plainの修正

Plain JPをRC3 Monoから派生させました。zero / zero.altの輪郭・ヒント・メトリクスを交換し、
zero機能と0+VS1の対応を追加・更新しました。ゼロ以外の字形・ヒント・メトリクス、
通常のアクセント配置と囲み記号のGPOSはRC3と同一です。
ss01 / cv01はゼロを反転し、Plain JPのzero機能は斜線入りを選択します。
0+VS1 (U+0030 U+FE00)は両方で斜線入りを選択します。
全角０は双方とも元の字形のままです。

## 日本語なし版の収録方針

次の5書体のRegular OTF実ファイルのcmapを比較しました。ウエイト違いを別書体として数えていません。

- [SF Mono](https://developer.apple.com/fonts/) — ローカルの公式配布OTF
- [Source Code Pro](https://github.com/adobe-fonts/source-code-pro) — 公式リポジトリ、commit固定
- [IBM Plex Mono](https://github.com/IBM/plex) — v6.4.0のOTF、commit固定
- [Fira Mono](https://github.com/mozilla/Fira) — 公式リポジトリ、commit固定
- [Intel One Mono](https://github.com/intel/intel-one-mono) — 公式リポジトリ、commit固定

5書体中3書体以上が収録する文字を採用し、Latin Extended-Aの欠けと、
収録アクセント文字を分解表記するための文字を補完しました。
比較対象の最新リリース全体を代表するという意味ではありません。各バージョン、取得URL、
commit、ハッシュ、ブロックごとの収録数、各文字の票数はcoverage-comparison.jsonに保存しています。

残すもの：ASCII、Latin-1と拡張ラテン文字、主要なギリシャ・キリル文字、結合アクセント、
句読点、通貨、上下付き数字・分数、一般的な数式・矢印・図形記号、罫線128字、ブロック32字。
Thaiブロックのバーツ通貨記号、Arabic Presentation Forms-BのBOMは共通記号として残します。
ギリシャ・キリル文字の拡張領域すべてを網羅する版ではありません。

外すもの：漢字、ひらがな、カタカナ、半角カナ、全角英数・句読点、CJK用の縦書き字形とIVS、
ハングル・注音・アルメニア文字・点字、囲みCJK文字、絵文字、大量の特殊記号、私用領域。
日本語はアプリの別フォントへフォールバックします。日本語なし版のspacing glyphは600、
結合文字・不可視制御は0の送りを維持しています。比較先から字形はコピーしていません。

## 検査と使い方

各ウエイトでRC3元データとの全残存字形の輪郭・ヒント・横送り・縦送りの一致を確認。
JP Monoの字形・GSUB・cmapはRC3から変更していません。Plain JPの変更はゼロ関係に限定。
全TTF / WOFF2の輪郭・ヒント・主要テーブルを照合し、ゼロ切り替えとVS1をHarfBuzzで確認しました。
収録文字の合成済み／分解表記の一致と、日本語なし版の全字形を9/12/14/16/20/32pxの
FreeTypeで元フォントと画素比較しています。結果はvalidation.json、見本はproof.pngです。

今回の新規描画検査はmacOS上のFreeType / HarfBuzzです。4.9の新しい書体名・
サブセットをWindowsの各アプリで再検証したという意味ではありません。
JPのゼロ以外は、既存RC3のWindows検証で使った字形・ヒント・配置データを保持しています。

ttf/内の必要なファミリをインストールしてください。旧Friday Mono（日本語入り）を使っていた場合は、
アプリの書体指定をFriday Mono JPへ変更します。新Friday Monoは旧4.8と同じ名前ですが、
収録範囲が変わった4.9です。旧版のファイルを同時に登録するとアプリが古いファイルを選ぶ場合があります。
web/にはWOFF2と3ファミリのCSSがあり、SHA256SUMS.txtでファイルを確認できます。
参照OTFのバイナリは配布パッケージに含みません。
