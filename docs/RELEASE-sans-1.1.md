# Friday Sans 1.1

Friday Sans Regular・Medium・Bold の計3本。内部バージョンは Version 1.100。
UPM 1000 の日本語プロポーショナル書体です。和文は全角 1000、欧文はプロポーショナル（カーニング付き）。
等幅の姉妹書体 Friday Mono と同じ和文（手描きの仮名を含む）を使っています。

## 配布物

- `ttf/`：Windows / macOS / Linux のインストール用 TTF。
- `web/`：ブラウザ用 WOFF2 と `friday-sans.css`。TTF フォールバック付き。
- `OFL.txt` / `licenses/`：ライセンス・原著作権表示。
- `font-manifest.json` / `SHA256SUMS.txt`：ファイル検証用。

## インストール

Windows：対象 TTF を右クリックして「インストール」。使用中のアプリを再起動してください。

macOS：対象 TTF を開いて Font Book でインストール。アプリを再起動してください。

Linux：対象 TTF を `~/.local/share/fonts/` に配置して `fc-cache -f` を実行します。

古い Windows アプリでは Medium が「Friday Sans Medium」という別ファミリに表示されます。
Regular / Bold のスタイルリンクを守るための仕様です。

## Web

`ttf/` と `web/` の相対位置を保ってサーバーへ配置します。

```html
<meta charset="utf-8">
<link rel="stylesheet" href="web/friday-sans.css">
<style>
  body {
    font-family: "Friday Sans", sans-serif;
    font-weight: 400;
    line-height: 1.7;
    font-synthesis: none;
  }
</style>
```

Regular=400、Medium=500、Bold=700。斜体はありません。

## 設計

| | 欧文 | 和文 |
|---|---|---|
| 元にしたフォント（アウトライン） | Inter 4.1（opsz 14） | Noto Sans CJK JP（Friday Mono と同じ工程） |
| 寸法の手本（数値の実測のみ） | SF Pro Text | ヒラギノ角ゴ |
| 大きさ | 大文字の高さを SF Pro Text と同じ 704.6/1000 に | ヒラギノの字面に合わせる |
| 太さ（縦画） | Regular 81.5 / Medium 101 / Bold 126 | 漢字 64.5 / 78.8 / 100 |
| 字間 | a〜z の平均送り幅を SF Pro Text と同じに | 全角 1000 |

太さは、SF Pro Text と同じ値（85 / 106 / 143）から出発し、和欧混植の見本を見て欧文を少し細く、Bold を全体に細く決め直しました。
行の高さはヒラギノ角ゴと同じ標準 1.5。余白を上下に均等に割り振っています（ascent 1130 / descent 370 / lineGap 0、全角の字面 880/−120 の中心＝行の中心）。

Inter のカーニング・合字・`case`・`ss01` 等の OpenType 機能はそのまま使えます。
縦書きは `vert` / `vrt2` と縦メトリクスを搭載しています。約物の詰め（`palt`）はまだありません。

## 1.0 からの変更

- 縦メトリクスのみ変更。1.0 はヒラギノと同じ 880 / −120 + lineGap 500 でしたが、Windows（DirectWrite・WPF など）は lineGap を行の片側にまとめて付けるため、ボタンや入力欄・エディタの行で文字が中央からずれていました。1.1 は lineGap を 0 にして、その 500 を上下に 250 ずつ振り分けています。標準の行の高さ（1.5）は変わりません。
- GDI 用の usWinAscent / usWinDescent も同じ 1130 / 370 にそろえ、GDI のアプリでも行の高さが 1.5 になるようにしました（1.0 では約 1.86）。この範囲からはみ出すのは縦書き専用のくの字点 〱 〲 だけで、GDI ではこの2字の端が切れることがあります。
- 字形・字幅・カーニング・OpenType 機能は 1.0 から一切変えていません。ヒント付きの描画結果も 1.0 と同じです。

## SF Pro・ヒラギノのアウトラインは使っていません

欧文の字形は Inter、和文の字形は Noto Sans CJK JP（と本プロジェクトの手描きの仮名）だけから作っています。
SF Pro Text とヒラギノ角ゴからは、大きさ・太さ・平均字幅・行の高さなどの**数値だけ**を測りました。
フォントファイルは配布物にも作業リポジトリにも入っていません。

大きさと太さを揃えたため文章では似て見えますが、字形そのものは別物です。
Regular の字を同じ高さに描いて重なる面積の割合を比べると（1.0 なら完全に同じ形。`sans/make_overlay.py` で再現できます）：

| | 元にしたフォントと | 手本と |
|---|---|---|
| 欧文 13 字（a e g t y R G Q J 1 $ & @） | Inter と 0.97 | SF Pro Text と 0.86 |
| 和文 12 字（永 国 書 東 語 機 鬱 あ い う え お） | Noto と 0.95 | ヒラギノ角ゴ W3 と 0.69 |

違いが目に見えるのは、欧文では `&` の上部と右下の脚・`J` の頭・`1` の旗・`a` `e` `t` の終筆、和文では `永` の払い・`機` の各部の位置・仮名の曲線などです。
SF Pro・ヒラギノの字形を含む比較画像は配布していません。

## ライセンス

SIL Open Font License 1.1。商用の文書・画像・Web サイト・アプリで使用できます。
フォントを再配布する場合は著作権表示と OFL を維持してください。フォント単体の販売は禁止です。
改変版の一次フォント名には Reserved Font Name「Friday」を使わず改名してください。
正確な条件は同梱 `OFL.txt` を参照してください。

使用ソース：Inter（OFL 1.1）、Noto Sans CJK JP（OFL 1.1、Reserved Font Name 'Source'）、および本プロジェクトの独自作図。

## 検証の位置づけ

macOS（CoreText）と Chrome で表示を確認し、FreeType でヒント付きの字が潰れないことを機械検査しています。
Windows 実機での表示は未検証です。
