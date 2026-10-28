# Friday Sans 3.1.0 / Friday Sans UI 3.1.0

Friday Sans 3.002 を基にしたローカルビルドです。Light・Regular・Medium・SemiBold・Bold の各5ウェイトを含みます。フォントの OpenType 内部バージョンは `3.100`（製品版 3.1.0）です。

- 欧文・数字の平らな足を基準線にそろえました。丸い字を −40 にする変更は行っていません。
- U+2026 `…` は、英語など Latin の組版では下寄り、日本語の組版では中央寄りの字形を使います。言語・文字種を判別できない単独文字は中央寄りで、アプリの組版方法によって表示が変わります。U+22EF `⋯` は中央寄りのままです。
- 丸付き数字・演算記号と `ss05` の囲み字形を、字幅に収まる大きさにしました。
- `⸺` と `⸻` を、それぞれ同書体の `—` の2倍・3倍の字幅にし、線の位置と太さをそろえました。

比較で以前見つかった Light の漢字の欠けや黒い塊は、3.000 のものを誤って 3.002 として調査した結果でした。正しい 3.002 では確認した19字がすでに修正されています。検証の詳細は `reports/verification.md` にあります。

## 再生成

`sans-v3.002` の配布 ZIP を展開し、フォントツールを用意したうえで、プロジェクトのルートから実行します。入力TTFはリポジトリ内の3.002マニフェストと全10書体の SHA-256 を照合します。

```powershell
./.venv/Scripts/python.exe -X utf8 scripts/sans30/build_sans_310.py --src work/sans-3002-input/FridaySans-3.002/ttf --out work/sans-3.1.0/ttf
./.venv/Scripts/python.exe -X utf8 scripts/sans30/test_sans_310.py work/sans-3002-input/FridaySans-3.002/ttf work/sans-3.1.0/ttf
./.venv/Scripts/python.exe -X utf8 scripts/sans30/make_web.py --ttf work/sans-3.1.0/ttf --out work/sans-3.1.0/web
./.venv/Scripts/python.exe -X utf8 scripts/sans30/package_sans_310.py --ttf work/sans-3.1.0/ttf --web work/sans-3.1.0/web --out work/sans-3.1.0/package
```

ウェブ用 lite は既存の JIS X 0208・Latin 等の部分集合であり、すべての文字を含むものではありません。フォントの内部ファミリー名は 3.002 と同じです。インストール時の既存版との競合に注意してください。
