# Friday Mono 5.0.3 / 2026-10-10

5.0.2 の **Light と LightItalic の線を太くした版**です。GitHub Release `mono-v5.0.3` で公開しました（5.0.2 は公開していないので、5.0.3 が 5.0.1 の次の公開版です）。ほかの8スタイルは、字形（座標）・字幅・cmap・行の値が 5.0.2 と同じです。ただし **`head.flags`・name テーブル・GSUB の FeatureParams は、全10スタイルで 5.0.2 と違います**（下の「3.」）。`head.flags` のビット 3 は、整数でない ppem での拡縮に効くため、**実機での確認は Light だけでなく Regular でも**お願いします。5.0 の説明は [../mono-5.0/README.md](../mono-5.0/README.md)、5.0.2 は [../mono-5.0.2/README.md](../mono-5.0.2/README.md) にあります。

> **確認してほしいこと：** Light の太さ。13〜24 px の Windows・Mac で Regular と並べて、この太さでよいか。細すぎる／まだ細いと感じたら、`MONO_LIGHT_GROW`（下記）を変えて作り直します。

## 何が変わったか

### 1. Light の線を 62 → 66 units にした

| ウェイト | 縦線の太さ（1000 units） | 前のウェイトとの差 |
|---|---:|---:|
| Light（5.0.2） | 62 | — |
| **Light（5.0.3）** | **66**（Italic は 65） | — |
| Regular | 80 | Light との差 **14**（5.0.2 は 18） |
| Medium | 92 | 12 |
| SemiBold | 104 | 12 |
| Bold | 123 | 19 |

- 5.0.2 の Light は Regular を 62 まで細らせた派生ウェイトで、Light と Regular の差だけが 18 と広く、13〜24 px では灰色に細く見えるため「ヒョロヒョロで出荷できる品質ではない」という判断でした（レビュー r3 [P1 #2]）。
- 輪郭を線幅で +5 units だけ外へ広げ（`scripts/derive_iosevka_weights.py` が Light を作ったときと同じ膨張）、基線・x 高さ・キャップ高・アセンダー・ディセンダーの上下の位置は元に戻します（`scripts/mono50/light_stem.py`）。高さは変わりません（x 高さ 521、キャップ高は 5.0.2 と同じ）。
- ブロック要素・網掛け・Powerline など、Regular・Medium・Bold で同じ形の字は触りません。
- **+5 より太くできなかった理由：** +6 と +7 では、ttfautohint が 10〜24 px で 7 と 9 の上端を他の数字と同じ画素の行にそろえられませんでした（数字の桁そろえ検査が失敗）。+5 は全サイズでそろいます。
- 作り直し：`MONO_LIGHT_GROW=5 py scripts/mono50/build_mono_50.py`。環境変数がなければ Light は 62 のままですが、下の「3.」の name・`head.flags`・FeatureParams の変更は入るため、**公開済みの 5.0.2 の ZIP とはバイトが一致しません**（5.0.2 は今の HEAD からは再現できません）。

### 2. 太くしたときに生じた針状の点を取った

B・§・Β・В・Ḃ・Ḅ・Ḇ（Light）と B・§・Ǫ・Ǭ・Ḅ（LightItalic）の、2 つのふくらみの合流点（B）や曲線の合流点（§・Ǫ）が、太くした輪郭で針状の小さな突起になりました。`spike_check.py` の基準（針の長さ 8〜80 units、角度 25° 未満）に当たった点を取り除きました。4.93 にあった針、設計どおりの針（`spike_review.py` に目視済みとして記録）は残します。

### 3. Fontspector（universal プロファイル）の指摘を直した

| 指摘 | 対応 |
|---|---|
| `head.flags` のビット 3（hinted なので ppem を整数に丸める）が立っていない | 全10スタイルで立てた |
| name の LICENSE_DESCRIPTION の末尾の空白 | 削った |
| Mac 用の name レコード | 外した（Windows 用のレコードに全部ある） |
| ss01 に説明の名前がない | ss01 と cv01（ゼロのスラッシュなし）に FeatureParams と名前を付けた |

残る指摘：U+1E30（Ḱ）・U+1E6E（Ṯ）の小文字がない（5.0 の文字の整理の結果）、`hhea.numberOfHMetrics` の推奨、WWS、ソフトハイフン、STAT。

## 検査結果（5.0.3）

- **公開5.0との描画差（独立検査）**：Light以外の8スタイルは輪郭・字幅・cmap・字形順が一致します。ただし5.0からはWinAscentが1000→1164に変わり、再ヒント付けで `cvt`・字形の命令も変わっています。FreeTypeの9〜24pxでは積みアクセントを中心に描画差があります。Regular・Boldの13px比較では明確な破綻は見られませんでしたが、全描画が不変という意味ではありません。ClearType実機は未確認です。

- `verify_mono_50.py`：失敗 0（1,062 字。輪郭の折れ 0、罫線のすき間 0、丸い字と平らな字の高さ差 0、数字の高さ、二重下線、シェーピング、WOFF2、隣のウェイトとの比較：最大 16 px）。Light の検査は、膨張後の値（縦線 +3〜+8）を確かめる形にしました。
- `compare_outlines.py`：Light・LightItalic は 4.93 との面積差が平均 8 %（最大 23.9 %：U+25CB。小さい輪郭）、上限 25 % で 0 字。他の8スタイルは 1 % を超える字 0。
- `spike_check.py`：未確認のとげ 0。
- **Windows GDI**（複製を使い、`GetFontData` で描画中のバイト列の一致を確認）：丸い字と平らな字の高さ差 0（10スタイル）、全字形の描画 16,263 ケース × 10 スタイル、エラー 0。
- **ブラウザ**：全10スタイルの WOFF2 を Chromium・Firefox・WebKit（Playwright）で読み込み、描画できることを確認（`scripts/qa/browser_check.py`）。
- **HarfBuzz**：5.0（5.0.2 と字形・字幅が同じ）と比べ、3,520 の組版（機能セット 22 × 横組み・縦組み × 8 つの見本文）で、字形列・送りの不一致 0（縦組みの y オフセットだけ、輪郭の太さに従って ±6 units 以内で変わる）。
- **独立した組版再検査**：結合文字を加えた10見本文で4,400件を比較。Light系の縦組みyオフセットのみ最大2unitsの差（242件）、ほかの字形列・送り・xオフセットは完全一致。縦yオフセットだけ2units許容して全件合格。検査は例外・比較漏れを不合格に修正しました（`reports/codex-review-2026-10-10.md`）。
- **FontForge**（`scripts/qa/ff_validate.py`）：自己交差している字形は Light 31（5.0 は 24）、LightItalic 37（5.0 は 59）。e・X・& などで、設計上の重なりが膨張で増えたものです（e・X・& を 520 px で目視：欠け・はみ出しなし）。極値に点がない字形は LightItalic 102（5.0 は 178）。
- **Fontspector**：上の表のとおり。

## 未確認

- ClearType の実画面（WPF・Office・Edge・Windows Terminal）、macOS・iOS・Android での Light の見え方。**公開後も、この確認は残っています。**
- 見本：`reports/proof-light-vs-regular.png`（Light 5.0.2・5.0.3・Regular を 13〜24 px で並べた。FreeType・グレースケール）、`reports/proof-styles.png` ほか。13〜24 px の比較は FreeType（ヒント適用、グレースケール）で、ClearType ではありません。

## 再生成

`FridayMono-4.93.zip`（正規配布。マニフェストの SHA-256 で照合）を `FridayFonts/` に置き、5.0 と同じ手順に環境変数を付けて実行します（[../mono-5.0/README.md](../mono-5.0/README.md) の「再生成」）。

```sh
MONO_LIGHT_GROW=5 py scripts/mono50/build_mono_50.py
py scripts/mono50/verify_mono_50.py
py scripts/mono50/compare_outlines.py
py scripts/mono50/spike_check.py
py scripts/mono50/proof_mono_50.py
MONO_LIGHT_GROW=5 py scripts/mono50/package_mono_50.py     # releases/mono-5.0.3/ と FridayMono-5.0.3.zip
```
