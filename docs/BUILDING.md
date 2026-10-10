# ビルド手順

Friday Fontsのビルドは、作者のローカル作業環境を前提にしています。このリポジトリを単体でcloneしただけでは、再ビルドできません。必要なもの：

| 必要なもの | 用途 |
|---|---|
| 隣の `Source/`（Iosevka・Noto Sans CJK JP・Inter） | 元にする書体 |
| 隣の `FridayFonts-WindowsTest/`・`comparisons/`・`InoriMono-v3-build/` | Windows対策の工程と、途中の作業ファイル |
| Python 3.12＋fontTools（[scripts/requirements-v47.txt](../scripts/requirements-v47.txt)） | ビルド本体 |
| ttfautohint・HarfBuzz（hb-shape）・FreeType | ヒント付けと検査 |
| Node.js＋Chlorophytum（[scripts/chlorophytum/package.json](../scripts/chlorophytum/package.json)） | 漢字のヒント付け |

SF Mono・ヒラギノは数値の測定にだけ使い、出力には入りません。これらはApple・SCREENのライセンスで再配布できないため、リポジトリにも含めていません。

以下のコマンドは、作業環境のルート（`FridayFonts/` の1つ上）で実行します。

## Friday Mono

R/M/B（4.91・4.92まで）：

```sh
InoriMono-v3-build/.venv/bin/python FridayFonts/scripts/build_mono_49.py
InoriMono-v3-build/.venv/bin/python FridayFonts/scripts/verify_mono_49.py
InoriMono-v3-build/.venv/bin/python FridayFonts/scripts/audit_italic_rc3.py
InoriMono-v3-build/.venv/bin/python FridayFonts/scripts/build_mono_492.py
```

字形の中心は [scripts/build_inori_v3.py](../scripts/build_inori_v3.py) です。測った数値は、すべてこのファイルの冒頭に定数として書いてあります。

- 欧文：Iosevkaを、全角2：半角1の枠に合わせて字幅と横線を調整します。
- 和文：Noto Sans CJK JPの可変軸から、漢字・ひらがな・カタカナを別々の太さで取り出します。
- 手描きかな：[scripts/drawings/](../scripts/drawings/) の線から作ります。

[scripts/validate.py](../scripts/validate.py) と [scripts/test_build.py](../scripts/test_build.py) が、ビルドの前提を検査します。

工程ごとのキャッシュは `.build-cache/mono/` に保存します。入力・コード・設定・ツールの版のハッシュが同じ工程は再利用し、`--no-cache` で無効にできます。

## Friday Mono 5.0

5.0は、配布済みの`FridayMono-4.93.zip`を入力にします。Iosevkaの再ビルドや和文の工程は通りません。手順は[releases/mono-5.0/README.md](../releases/mono-5.0/README.md)の「再生成」にあり、コマンドは`FridayFonts/`で実行します。

| スクリプト（`scripts/mono50/`） | 役割 |
|---|---|
| `coverage_votes.py` | 6書体の収録文字を数え、残す・削る・足す文字を`coverage.json`に書く |
| `inherited_fixes.py` | 4.93の派生ウェイトで向きが逆になった輪郭（白抜きのアキュート、切れた ogonek、チルダの切れ込み）と、Light の Ђ・℮ の崩れ、Light の ½ の分母を直す |
| `outline_repair.py` | 丸い字の端の折れ線と重複点を直す（ttfautohintが丸い字を丸いと判定できるようにする） |
| `heights.py` | 大文字・数字・上に伸びる小文字・括弧などの高さをSF Monoの比率（キャップ高 / x-height 1.333、上端 / キャップ高 1.047）に合わせる。数字は平らな端をH、丸い端をOの高さにそろえる。縮めた分は縦方向にだけ太らせて横画の太さを保つ |
| `build_mono_50.py` | 文字の整理、輪郭の修正、罫線の調整、記号の追加、行の数値・名前を設定し、ttfautohintでヒントを付ける |
| `verify_mono_50.py` | 文字セット、輪郭、高さ揃え、数字、罫線、二重下線、シェーピング、WOFF2の検査 |
| `compare_outlines.py` | 高さを変えていない字について、4.93と輪郭の面積差を比べる |
| `spike_check.py` | 輪郭に針状のとげがないか調べる（目で確認済みの字は理由付きで一覧にしてある） |
| `light_stem.py` | **5.0.3 の候補**：`MONO_LIGHT_GROW=5` のとき、Light・LightItalic の線を +5 units 太らせ（基線・x 高さ・キャップ高などは元の位置へ戻す）、太らせで生じた針状の点を取る。環境変数なしでは Light は 5.0.2 のまま（ただし name・`head.flags`・ss01 の FeatureParams の変更は入るので、公開済み 5.0.2 の ZIP とはバイトが一致しない） |
| `spike_review.py` | 目視済みの設計どおりの針（`spike_check.py`・`light_stem.py` が使う） |
| `windows/prepare_gdi_copy.py` | 名前表だけを変えた検査用の複製を作る（同名の旧版が入っていても、それを描かないため） |
| `windows/gdi_heights.ps1`・`windows/gdi_all_glyphs.ps1` | Windows GDIで、丸い字の高さと全字形の描画を検査する（プライベート読み込み。描画中のフォントが対象ファイルと一致することを`GetFontData`で照合する） |
| `weight_ladder.py` | 直立5ウェイトを描き、隣り合うウェイトの間で、4 pxより離れたインクのかたまりが100 pxを超える字を探す（自分自身との比較では見つからない、入力から引き継いだ壊れ用。`verify_mono_50.py`から呼ぶ） |
| `ligatures.py` | **5.1.0 の候補**：`MONO_LIGATURES=1` のとき、コーディング合字 27 種（`ss02`）を描いて GSUB に足す。字は各スタイルの `= - < > /` から作る（棒の太さ・山形の角度と線の太さ・先端の平らな部分を字から測る。斜体は傾きを戻してから組み、また傾ける）。先頭の n−1 文字は空グリフ `lig.spc`、最後の文字は左へはみ出す合字グリフ（advance 600）。重なりは `removeOverlaps` で結合。環境変数なしでは何も変わらない |
| `proof_ligatures.py` | 合字の見本（`proof-ligatures.png`＝Regular の合字なし／あり、`proof-ligatures-styles.png`＝全10スタイル）。`--paper <Paper Mono の ttf>` で参考列つきの比較図（見るだけ。フォントには使わない） |
| `package_mono_50.py` | 検査結果を確認してから候補版の配布物を作る。`MONO_LIGHT_GROW=5` では `releases/mono-5.0.3/` と `FridayMono-5.0.3.zip`、さらに `MONO_LIGATURES=1` では `releases/mono-5.1.0/` と `FridayMono-5.1.0.zip`（`lig_check.py` が通らないと作らない）。環境変数なしでは5.0.2。旧版の記録は別ディレクトリに残す |

出力は`work/mono-5.0/`（git管理外）です。

## Friday Sans

[scripts/sans/build_sans_cjk.py](../scripts/sans/build_sans_cjk.py) が、Monoと同じ和文工程を1000 unitの枠で実行します。[scripts/sans/build_sans.py](../scripts/sans/build_sans.py) がInterの欧文と合成します。

2.0以降の手順：
1. 統合ビルド：`comparisons/unified-sans-trial`
2. 2.1の修正（合成半濁点、𠮷）：[scripts/sans/build_2_1.py](../scripts/sans/build_2_1.py)
3. Windows対策とRC1〜RC3：`FridayFonts-WindowsTest`

## Light / SemiBold（Mono 4.93・Sans 2.5）

R/M/Bと同じ工程を、2つのウェイトでもう一度通します。工程は [scripts/weights/build_weights.py](../scripts/weights/build_weights.py) にまとめてあり、次の順に実行します。

```sh
PY=InoriMono-v3-build/.venv/bin/python
W=FridayFonts/scripts/weights/build_weights.py
$PY $W iosevka        # 欧文マスター（下記）
$PY $W mono-raw       # Monoの組み立て
$PY $W mono-finish    # ttfautohint・漢字ヒント（初回は1書体あたり約1〜2時間）
$PY $W mono-v48
$PY $W sans-cjk
$PY $W sans-unity --hint
$PY $W sans-20
$PY $W sans-21
$PY $W ws-mirror      # FridayFonts-WindowsTest-weights を作る
$PY $W ws-caps
$PY $W ws-guard
$PY $W ws-balance
$PY $W ws-ui
$PY $W ws-lab
$PY $W ws-rc
$PY FridayFonts/scripts/weights/release_mono.py
$PY FridayFonts/scripts/weights/release_sans.py
$PY FridayFonts/scripts/weights/verify_mono_weights.py
$PY FridayFonts/scripts/weights/audit_weights.py FridayFonts/releases/mono-4.93 FridayFonts/releases/sans-2.5
```

既存のスクリプトはコピーして読み込み、スタイル名と入出力フォルダだけを書き換えて実行します。書き換えは文字列で行い、一致しなければ止まるようにしてあります。元のファイルや出荷済みの配布物には書き込みません。

### Iosevka Light / SemiBoldについて

IosevkaのLight・SemiBoldは、Iosevka本来のビルド（npm）ではありません。既存のRegular・Mediumの輪郭を目標の線幅まで細らせ・太らせて作っています（[scripts/derive_iosevka_weights.py](../scripts/derive_iosevka_weights.py)）。

- 基準線・x-height・キャップ高・アセンダー・ディセンダーの上下位置は、元の位置へ戻します。
- 全ウェイトで同じ形の字は、元の形のまま使います。ブロック要素、網掛け、Powerline記号など627字です。

## 検査

各版の `reports/` に、次の結果を保存しています。

- 全グリフの描画検査：FreeType、ヒント方式2種、9〜32px
- 組版の検査：HarfBuzz
- 太さの段階：`weight-audit.json`
- 見本画像

Windows実機での確認結果は、FridayFonts-WindowsTestの報告書にあります。

## Friday Sans 3.0

3.0は、配布済みの`FridaySans-2.5.zip`を入力にします（Inter・Noto Sans CJK JPのソースは使いません）。手順は[releases/sans-3.0/README.md](../releases/sans-3.0/README.md)の「再生成」にあります。

| スクリプト（`scripts/sans30/`） | 役割 |
|---|---|
| `soften.py` | 尖った角に短い2次曲線の面取りを入れる（凸は線幅の0.19倍、凹は0.09倍） |
| `build_sans_30.py` | Light の壊れた漢字の作り直し（`repair_light.py`・`light_repair.json`）、≒・ℊ・結合記号の幅・ss/cv の名前（`fixups.py`）、面取り、輪郭のオフセット（太らせ、字ごとに二分探索。0.5 unit で接する輪郭は融合を許す）、ヒント削除、`gasp`、Sans UIの字面拡大（em 1050→1010読み替え）、Win値・ベンダーID・空白幅・lsb/tsb・版の修正、Mac名・ltag の削除、太さの段差の仕上げ（`ladder_pass`）、GDEF の mark クラス。`--no-ladder`・`--ladder-only`・`--finish-only` で後半だけ実行できる |
| `xweight.py` | 隣のウェイトとの比較（楔・とげ・欠けた画）。`verify_sans_30.py` から呼ぶ |
| `verify_sans_30.py` | 2.5との字形ごとの比較、書体ごとのテーブル・メトリクスの確認、隣のウェイトとの比較、太さの段差。全部で約25分（`--no-weights` で比較と段差を省く） |
| `render_check.py` | 全収録文字をFreeTypeで9〜24 pxに描画し、空描画・つぶれを検出 |
| `make_web.py` | WOFF2（全字形版と、JIS X 0208＋欧文の軽量版）とCSS |
| `proof_sans_30.py` | 太さの見本、Light の作り直しの前後、≒ の見本を描く |
| `package_sans_30.py` | ZIPと`releases/sans-3.0/`を作る |

## 品質検査のツール（`docs/FONT-TOOLS.md`）

`scripts/qa/` が、導入済みのツールを使います（PowerShell で `. ./scripts/activate-font-tools.ps1` してから）。

| スクリプト・ツール | 内容 |
|---|---|
| `fontspector -p universal <ttf...> --json out.json` | Google Fonts 系の universal プロファイル。Mac 名・ltag・空白・`head.flags`・名前の欠けなどを拾う |
| `scripts/qa/browser_check.py` | WOFF2 を Chromium・Firefox・WebKit（Playwright）で読み込み、見本を描いて PNG にする |
| `scripts/qa/lig_check.py --dir <ttf dir> [--baseline <旧版の ttf dir>]` | Mono のコーディング合字（`ss02`）の検査：27 種の組版（空グリフ＋合字）・続く並びが合字にならないこと・`ss01` との併用・輪郭（結合済み・向き・はみ出し）。`--baseline` で、合字なしの組版が旧版と同じことも確かめる |
| `scripts/qa/lig_browser.py --web <web dir> --out <dir>` | 合字を Chromium・Firefox・WebKit で、オン／オフを描き比べる |
| `scripts/qa/shape_regress.py --old <dir> --new <dir>` | 2 つのビルドを HarfBuzz で組み比べる（字形列・送り・オフセット） |
| `scripts/qa/ff_validate.py` | FontForge の検査（自己交差・極値の欠け）。`scripts/fontforge.cmd -lang=py -script ...` で実行 |
| `diffenator2 diff -fb <旧> -fa <新> --no-diffbrowsers` | 旧版と新版の字形差の HTML（実行すると `build.ninja` ができるので、ルートに残さない） |

## Sans 3.002 の作り直しの順序

このWindowsワークスペースでは [FONT-TOOLS.md](FONT-TOOLS.md) の `.venv` に、
ビルド・検査用のBrotli、SciPy、scikit-imageを含めています。
以下の `python` は `.venv/Scripts/python.exe -I -X utf8` に置き換えてください
（`work/sans-3.0/` 内では `../../.venv/Scripts/python.exe -I -X utf8`）。
Mono 5.0.3 をPowerShellで再生成するときは、ルートで
`$env:MONO_LIGHT_GROW='5'` を設定して同じPythonから `scripts/mono50/build_mono_50.py` を実行します。
既存出力を保持するレビューでは `$env:MONO_OUT='work/codex-review/mono/rebuild-complete'` のように
新しい出力先を指定してください。設定した環境変数は、検査・パッケージ生成まで同じ値を使います。

```sh
cd work/sans-3.0
python ../../scripts/sans30/build_sans_30.py --src x/FridaySans-2.5/ttf --out ttf     # 約35分（10並列＋段差のパス）
python ../../scripts/sans30/verify_sans_30.py --src x/FridaySans-2.5/ttf --out ttf --report verify.json
python ../../scripts/sans30/render_check.py --out ttf
python ../../scripts/sans30/make_web.py --ttf ttf --out web
python ../../scripts/sans30/proof_sans_30.py --ttf ttf --src x/FridaySans-2.5/ttf --out stage/reports
# stage/reports に verify.json・build-log のほか、監査（audit/）・ブラウザ確認・組版比較の結果を置いてから
cd ../.. && python scripts/sans30/package_sans_30.py                                 # FridaySans-3.002.zip と releases/sans-3.0/
```
