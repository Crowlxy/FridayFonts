# scripts

Friday MonoとFriday Sansを作るためのスクリプトとデータです。手順は[docs/BUILDING.md](../docs/BUILDING.md)を参照してください。現行のビルド（Mono 5.x・Sans 3.x）が使うものだけを置いています。旧版（Mono 4.x・Sans 2.x）のスクリプトは、削除の経緯が[docs/CLEANUP-2026-10-28.md](../docs/CLEANUP-2026-10-28.md)にあります。

| 場所 | 内容 | 使うビルド |
|---|---|---|
| `mono50/` | Friday Mono 5.x。配布済み4.93のZIPから、輪郭修正・ヒント再付与・罫線調整・収録文字の票決・Light 太らせ・コーディング合字、検査、パッケージ、Windows GDI検査（`windows/`） | Mono 5.0〜5.1 |
| `sans30/` | Friday Sans 3.x。配布済み2.5（3.1.0は3.002）のTTFから、Lightの作り直し・面取り・太らせ・基準線・三点リーダー・丸付き字形など、検査、WOFF2、パッケージ | Sans 3.0〜3.1.0 |
| `qa/` | ブラウザ読み込み、HarfBuzzの組版の回帰、FontForgeの検査、合字の検査 | 共通 |
| `build_inori_v3.py` | Monoの中心となるビルド。測定値の定数、欧文・和文・手描きかなの組み立て（`mono50/`が定数と関数を使う） | Mono 5.x |
| `validate.py` | ビルドの前提と出力の検査 | Mono 5.x |
| `rehint.py` | 欧文のヒント付け（ttfautohint） | Mono 5.x |
| `derive_iosevka_weights.py` | Mono Light / SemiBoldの欧文マスター | Mono 5.x |
| `release_features.py`・`thin_ki.py`・`fix_voiced_bodies.py`・`build_underline_trial.py` | `build_inori_v3.py`・`mono50/`が呼ぶ部品 | Mono 5.x |
| `tools/` | 輪郭処理（`shapes.py`）、手描きかな（`handdrawn.py`・`shared_master.py`）、測定 | Mono 5.x |
| `drawings/` | 手描きかなの原画と、承認済みの輪郭データ | Mono 5.x |
| `check-font-tools.py`・`activate-font-tools.ps1`・`requirements-font-tools*.txt`・`fontforge.cmd` | 品質検査ツールの導入確認と実行（[docs/FONT-TOOLS.md](../docs/FONT-TOOLS.md)） | 共通 |
| `OFL.txt` | フォントに埋め込むライセンス本文（Mono用） | Mono 5.x |

`build-weights/`・`fonts/` などの生成物はGitの対象外です。
