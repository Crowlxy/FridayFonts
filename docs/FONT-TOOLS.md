# ローカルのフォントツール

このWindowsワークスペースに12ツールをインストール済みです。Pythonは
`.venv/Scripts/python.exe`（3.14）を使います。システムPythonでは読み込めません。

| ツール | 導入版 | 実行方法・Pythonモジュール |
|---|---|---|
| FontTools | 4.66.1 | `python -m fontTools.ttx` / `fontTools` |
| ufoLib2 | 0.19.0 | `ufoLib2` |
| Diffenator 2 | 0.5.0 | `diffenator2` |
| fontmake | 3.12.1 | `fontmake` |
| HarfBuzz | 14.6.0 | `hb-shape`、`hb-view`、`hb-subset` / `uharfbuzz` 0.56.3 |
| skia-pathops | 0.9.2 | `pathops` |
| Playwright | 1.63.0 | `playwright` / Chromium・Firefox・WebKit導入済み |
| Fontspector | 1.9.0 | `fontspector` |
| vttLib | 0.12.1 | `python -m vttLib` |
| FreeType | 2.13.2 | `freetype`（freetype-py 2.5.1、DLL同梱） |
| ttfautohint | 1.8.4.16-eb64 | `ttfautohint` / `ttfautohint-py` 0.6.1 |
| FontForge | 20251009 | `fontforge -lang=py -script <script.py>` |

PowerShellでプロジェクトのルートから実行します。

```powershell
. ./scripts/activate-font-tools.ps1
python scripts/check-font-tools.py
```

スクリプト実行ポリシーで読み込めない場合は、PowerShellを
`pwsh -NoProfile -ExecutionPolicy Bypass` で起動してから上記を実行します。
恒久的な実行ポリシーやユーザーPATHの変更は不要です。
AIのシェル呼び出しごとに有効化してください。

有効化せずに使う場合のパス：

```powershell
./.venv/Scripts/python.exe -m vttLib --help
./.venv/Scripts/diffenator2.exe --help
./.venv/Scripts/fontmake.exe --version
./work/font-tools/harfbuzz/harfbuzz-win64/hb-shape.exe --version
./work/font-tools/fontspector/fontspector-1.9.0-x86_64-pc-windows-gnu/fontspector.exe --version
./.venv/Lib/site-packages/ttfautohint/ttfautohint.exe --version
./scripts/fontforge.cmd -lang=py -c 'import fontforge; print(fontforge.version())'
```

Playwrightを直接Pythonから使う場合は
`PLAYWRIGHT_BROWSERS_PATH` をプロジェクトの `work/font-tools/browsers` の
絶対パスに設定します。有効化スクリプトと確認スクリプトは自動設定します。
FontForgeは同梱Python 3.12を専用ラッパー内だけで使用します。

再導入用のPython依存一覧は `scripts/requirements-font-tools.txt`、
導入済み全パッケージの固定版は `scripts/requirements-font-tools.lock.txt` です。
Diffenator 2のprotobuf要件に合わせ、gflanguagesとglyphsetsを固定しています。
WOFF2生成用のBrotliと、全字形・ウェイト比較用のSciPy／scikit-imageも含みます。
フォントのビルド・検査は `.venv/Scripts/python.exe -I -X utf8` で実行できます。

※2026-11-06の監査メモ：このlockは再構築用の記録で、現在の `.venv`（8パッケージ。brotli 1.2.1・pillow 13.0.0・numpy 2.5.4など）とは一致しません。`.venv` 自体に既知の脆弱性はありませんが、lockのまま再構築すると次の既知の脆弱性を含む版が入ります（括弧内は修正版）：pillow 12.3.0（13.0.0）、filelock 4.0.12（4.2.1）、brotli 1.2.0（1.2.1）、certifi 2026.7.22（2026.10.18）、setuptools 84.0.0（84.1.0）、protobuf 3.20.3（4.25.8以降）。protobufはDiffenator 2との互換のための意図的な固定なので据え置きます。lockを更新する場合は、完全環境を新規に作って動作確認してから行います。

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r scripts/requirements-font-tools.lock.txt
```

ネイティブ配布物の取得元：
[Fontspector](https://github.com/fonttools/fontspector/releases/tag/fontspector-v1.9.0)、
[HarfBuzz](https://github.com/harfbuzz/harfbuzz/releases/tag/14.6.0)、
[FontForge](https://github.com/fontforge/fontforge/releases/tag/20251009)。
取得したアーカイブ・インストーラーは `work/font-tools/` に保存しています。

確認済み：Pythonモジュール10種の読み込み、`pip check`、主要CLIの起動、
FontForgeのPython実行、Playwrightの3ブラウザーで空の確認ページの表示。
フォントファイルのレビュー・変更は行っていません。
