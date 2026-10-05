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
