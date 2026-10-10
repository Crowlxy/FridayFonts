# Friday Mono 5.1.0（候補・未承認）/ 2026-10-11

5.0.3 に、**コーディング用の合字（OpenType の `ss02`「Coding ligatures」）を足した候補**です。ユーザーの承認が済むまで、公開しません（公開は GitHub Release `mono-v5.1.0` の作成になります）。**`ss02` を指定しない限り、5.0.3 と字形・字幅・組版が同じです**（下の「検査結果」の 4,400 件）。5.0.3 の説明は [../mono-5.0.3/README.md](../mono-5.0.3/README.md) にあります。

> **確認してほしいこと：** 実機（Windows Terminal・VS Code・Mac）で `ss02` を有効にして、合字の形・太さ・カーソルの動きがよいか。形を直したい合字や、足してほしい並びがあれば知らせてください。

## 何が変わったか

### 合字（`ss02`）

標準ではオフです。使うときだけ、アプリで `ss02` を有効にします。

```json
// VS Code（settings.json）。ゼロの斜線を消す ss01 と併用するなら 'ss01', 'ss02'
"editor.fontLigatures": "'ss02'"
```

```json
// Windows Terminal（settings.json の font）
"font": { "face": "Friday Mono", "features": { "ss02": 1 } }
```

```css
/* Web */
code { font-feature-settings: "ss02"; }
```

`ss01`（ゼロの斜線を消す）は今までどおりです。`ss02` と一緒に使えます。

| 種類 | 並び |
|---|---|
| 等号・不等号 | `==` `===` `!=` `!==` `=/=` `/=` |
| 比較 | `>=`（≥） `<=`（≤） |
| 矢印 | `->` `-->` `=>` `==>` `<-` `<--` `<->` `<-->` `<=>` `<==` |
| 二重の山形 | `>>` `<<` `>>=` `<<=` `=>>` `=<<` |
| パイプ | `\|>` `<\|` `<\|>` |

計 27 種。見本：[reports/proof-ligatures.png](reports/proof-ligatures.png)（Regular、合字なし／ありの比較）、[reports/proof-ligatures-styles.png](reports/proof-ligatures-styles.png)（全10スタイル）。

**仕組み。** 1 文字ごとの 600 units の幅はそのままです。n 文字の並びでは、先頭の n−1 文字を中身のない空のグリフ（`lig.spc`）に置き換え、最後の 1 文字を、左側へはみ出して n 文字ぶんの形を描く合字グリフに置き換えます（Paper Mono や Fira Code と同じ方法）。端末やエディターは文字ごとの幅を信じているので、カーソルや選択の位置はずれません。

**形は Friday Mono 自身の字から作った。** 棒（`-` `=`）の太さ・位置、山形（`<` `>`）の角度・線の太さ・先端の平らな部分は、各ウェイトの字から測っています。10 スタイルとも、同じ設計から太さだけ変わります（斜体は、字を傾きなしに戻して組み、また傾けています）。重なった部品は 1 本の輪郭に結合しました（`==` は 2 本の輪郭、`!=` は 1 本）。

**Paper Mono の使い方。** どの並びを合字にするか、どんな形にするか（矢印の軸が山形の先に届く、等号の棒がつながる、≠ は斜線が貫く、≥・≤ は山形と棒、パイプは三角形）の参考にしました。**Paper Mono（SIL OFL 1.1）の輪郭・GSUB は一切使っていません**（形は全部、Friday Mono の字から作り直しています）。

**同じ並びが続くとき。** `====`・`->>`・`<<<`・`>>>` のように、合字になる並びの先頭か末尾の文字がさらに続くときは、どれも合字にしません（意図しない部分だけが合字になるのを避けるため）。`<<-` は `<<` だけが合字になり、`<<=>>` は `<<=` と `>>` になります。

**Paper Mono の 53 種のうち、実装していないもの。** 波線（`~`）を使うもの（`~>` `<~` `~~` `<~>` `-~` `~-` `=~` `!~` など）、`::` `:::` `:=` `..` `..=` `.=`、`#=` `/==` `=:=` `=!=` `<::` `<!--` など。棒・山形・三角形で作れる 25 種に `==>` `<==` を足した 27 種に絞りました。

### 版名

`Version 5.100`（5.1.0）。内部の版は 5.003 → 5.100。

## 検査結果（5.1.0）

- **合字なしの組版は 5.0.3 と同じ**：`shape_regress.py` で、5.0.3 の ZIP の TTF と比べ、4,400 の組版（機能セット 22 × 横組み・縦組み × 10 見本文 × 10 スタイル）の不一致 0。
- **合字の検査**（`scripts/qa/lig_check.py`、10 スタイル）：27 種すべてで、`ss02` を入れると「空グリフ × (n−1) ＋ 合字 ＋ 次の文字」になり、送りはすべて 600、`ss02` なしでは素の文字になる。続く並び（`====` など）が合字にならない、`ss01` と `ss02` の併用、合字グリフに輪郭がある・左右が n 文字ぶんに収まる・輪郭の向きが字と同じ・重なりがない、空グリフが cmap に載っていない。失敗 0。
- `verify_mono_50.py`：失敗 0（1,062 字。輪郭の折れ 0、罫線のすき間 0、丸い字と平らな字の高さ差 0、数字の高さ、二重下線、シェーピング、WOFF2、隣のウェイトとの比較：最大 16 px）。
- `compare_outlines.py`：Light・LightItalic は 4.93 との面積差が平均 8 %（上限 25 % で 0 字）、他の 8 スタイルは 1 % を超える字 0。
- `spike_check.py`：未確認のとげ 0（合字のグリフも対象）。
- **Windows GDI**（複製を使い、`GetFontData` で描画中のバイト列の一致を確認）：丸い字と平らな字の高さ差 0（10 スタイル）、全字形（合字・空グリフを含む 1,279）の描画 16,627 ケース × 10 スタイル、エラー 0。
- **ブラウザ**（`scripts/qa/lig_browser.py`）：全10スタイルの WOFF2 を Chromium・Firefox・WebKit（Playwright）で読み込み、`ss02` をオン／オフにして描いた。合字の行はすべて変わり、合字にならない行はすべて同一。見本：`reports/FridayMono-ss02-*.png`。
- **Fontspector**（universal プロファイル、`reports/fontspector-5.1.txt`）：5.0.3 との差は `contour_count` の WARN だけ（6 スタイル。合字グリフの名前 `equal_equal_equal.liga` などから期待される輪郭数と違うという統計上の目安）。FAIL は 5.0.3 と同じ。

## 未確認

- **実機での表示**：Windows Terminal（DirectWrite）・VS Code・Mac・Linux の端末で、合字が崩れずに出るか、カーソル・選択・折り返しがずれないか。**承認に必要なのはこの確認です。**
- **合字が外せないアプリ**：`ss02` の指定ができないアプリでは、合字は出ません（標準でオフなので、今までどおりです）。
- **テキストのコピー・PDF の文字抽出**：空グリフ（`lig.spc`）は文字に対応させていないため、合字を含む文を PDF にして文字を抽出すると、先頭の n−1 文字が落ちることがあります（ブラウザやエディターでのコピーは、元の文字列を使うので影響しません）。
- **`>>=` と `=<<`**：棒が山形の腕にそのままつながる形で、Paper Mono の同じ並びより少し粗く見えます（形は読めます）。細部は見本を見て直します。
- Fontspector の `contour_count` の WARN は、上のとおり名前による目安です。

## 再生成

`FridayMono-4.93.zip`（正規配布。マニフェストの SHA-256 で照合）を `FridayFonts/` に置き、5.0.3 の手順に環境変数を付けて実行します（[../mono-5.0.3/README.md](../mono-5.0.3/README.md)）。

```sh
export MONO_LIGHT_GROW=5 MONO_LIGATURES=1 MONO_OUT=work/mono-5.1
.venv/Scripts/python.exe scripts/mono50/build_mono_50.py
.venv/Scripts/python.exe scripts/mono50/verify_mono_50.py
.venv/Scripts/python.exe scripts/mono50/compare_outlines.py
.venv/Scripts/python.exe scripts/mono50/spike_check.py
.venv/Scripts/python.exe scripts/mono50/proof_mono_50.py
.venv/Scripts/python.exe scripts/mono50/proof_ligatures.py
.venv/Scripts/python.exe scripts/qa/lig_check.py --dir work/mono-5.1/ttf --baseline <5.0.3 の ttf フォルダ>
.venv/Scripts/python.exe scripts/qa/lig_browser.py --web work/mono-5.1/web --out work/mono-5.1/qa-lig
# Windows GDI（prepare_gdi_copy.py → gdi_heights.ps1・gdi_all_glyphs.ps1）は docs/BUILDING.md
.venv/Scripts/python.exe scripts/mono50/package_mono_50.py     # releases/mono-5.1.0/ と FridayMono-5.1.0.zip
```
