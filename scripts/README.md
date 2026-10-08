# scripts

Friday MonoとFriday Sansを作るためのスクリプトとデータです。手順は[docs/BUILDING.md](../docs/BUILDING.md)を参照してください。

| 場所 | 内容 |
|---|---|
| `build_inori_v3.py` | Monoの中心となるビルド。測定値の定数、欧文・和文・手描きかなの組み立て |
| `validate.py`・`test_build.py` | ビルドの前提と出力の検査 |
| `rehint.py`・`cjkhint.py` | ヒント付け（欧文：ttfautohint、漢字：Chlorophytum） |
| `build_mono_49.py`・`build_mono_492.py`・`italic_rc3.py` | Mono 4.9〜4.92の派生（JP / Plain JP / 日本語なし、Italic、行の高さ） |
| `derive_iosevka_weights.py`・`finish_weights_mono.py` | Mono Light / SemiBoldの欧文マスターと仕上げ |
| `weights/` | Light / SemiBoldの全工程と、4.93・2.5の書き出し・検査 |
| `mono50/` | Friday Mono 5.0（欧文のみ）。4.93から輪郭修正・ヒント再付与・罫線調整・収録文字の票決、検査とWindows GDI検査 |
| `sans/` | Friday Sansのビルド（和文・Inter合成・2.1の修正・試作） |
| `tools/` | 輪郭処理（`shapes.py`）、手描きかな（`handdrawn.py`・`shared_master.py`）、測定 |
| `drawings/` | 手描きかなの原画と、承認済みの輪郭データ |
| `chlorophytum/` | 漢字ヒントの設定（ウェイトごとの線幅） |
| `windows-4.91/`・`windows-smoke-test.ps1` | Windowsでの確認用ツール |
| `OFL.txt`・`sans/OFL.txt` | フォントに埋め込むライセンス本文（Mono用・Sans用） |
| `rc3-italic/` | Italic RC3の検査記録 |

`build-weights/`・`fonts/` などの生成物はGitの対象外です。
