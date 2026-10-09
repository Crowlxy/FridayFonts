# Friday Mono 5.0.1 / 2026-10-09

5.0 の修正版です。2026-10-09 の品質レビュー（[reviews/2026-10-09.md](../../reviews/2026-10-09.md)）で見つかった、Windows GDI での重ねアクセントの欠けを直しました。字形・字幅・ヒントの設計は 5.0 と同じです。5.0 の説明は [releases/mono-5.0/README.md](../mono-5.0/README.md) にあります。

## 5.0 からの変更

### GDI で重ねアクセントの上端が欠ける問題

- 症状：Windows GDI（`TextOut`）で、Ǻ・Ấ・Ắ・Ễ・Ỗ など、アクセントを重ねた大文字の上端が欠けていました。48・96 px でははっきり見えます。全10スタイルで、19字の輪郭が `usWinAscent` を超えていました。
- 原因：`usWinAscent` / `usWinDescent` を計算するとき、Latin Extended Additional や U+01FA などを対象から外していました。さらに、合成字形（例：U+01D9）の外接矩形が古い値のままで、Bold 系は 1〜3 units 足りませんでした。cmap にない字形（合字・異体字など）も、対象から外れていました。
- 修正（`scripts/mono50/build_mono_50.py` の `family_win`）：cmap にない字形も含む全字形について、描画した輪郭から上端・下端を求めます。
- 結果：全スタイルで `usWinAscent` / `usWinDescent` が 1000 / 331 から **1164 / 331** になりました。全字形の輪郭がこの範囲に収まります。
- 副作用：GDI を使うアプリの行の高さが、約1.33em から約1.49em に増えます。`hhea` と `OS/2` の Typo 値（968 / −312、1.28em）は 5.0 と同じで、DirectWrite・CoreText・ブラウザの行の高さは変わりません。
- ヒント：ttfautohint を再実行しました。`usWinAscent` と行の上端（968）の間隔は、32 units 以上のままです。

### 検査の追加・修正

- `verify_mono_50.py` に、「`usWinAscent` / `usWinDescent` が全字形（非 cmap 含む）の輪郭を覆う」検査を追加しました。
- **GDI 検査が同名の旧版を描いても成功していた問題**：この PC には旧版の Friday Mono が `C:\Windows\Fonts` に入っていて、同じファミリー名のためプライベート読み込みしたフォントではなく旧版が選ばれていました。GDI スクリプトに `GetFontData` で、描画中のフォントのバイト列が検査対象ファイルと一致することを照合する処理を加え、不一致なら失敗にしました（`GdiHeights.cs`、`windows-4.91/GdiAudit.cs`）。
- 検査用に、名前表だけを書き換えた複製を作る `scripts/mono50/windows/prepare_gdi_copy.py` を追加しました。名前表以外の全テーブルが配布ファイルと一致することも確認します。GDI の検査はこの複製に対して行います。
- 5.0 の記録にある GDI の数値（丸い字の高さ・全字形描画）は、この PC の旧版を測っていた可能性があります。5.0.1 の数値は、照合に通った実ファイルの結果です。

## 検査結果

- `verify_mono_50.py`：失敗 0（1,062字、輪郭の折れ0、罫線のすき間0、丸い字と平らな字の高さ差0、数字の高さ、二重下線、シェーピング、WOFF2）
- `compare_outlines.py`：4.93 との面積差が1%を超える字は0
- `spike_check.py`：未確認のとげは0
- Windows GDI（複製を使い、`GetFontData` で描画中のバイト列の一致を確認）：丸い字と平らな字の高さ差 0（9〜32 px、10スタイル）、全字形の描画 16,263 ケース × 10スタイル、エラー 0

未確認：GDI でのアクセントの目視確認（レビューの再現スクリプト `gdi-proof.ps1` での再実行）と、アプリ上の ClearType の目視確認はまだです。

## 再生成

手順は 5.0 と同じですが、GDI の2つのスクリプトの前に `py scripts/mono50/windows/prepare_gdi_copy.py work/mono-5.0/ttf work/mono-5.0/gdi-copy` を実行し、`-Dir work/mono-5.0/gdi-copy` で呼びます。`scripts/mono50/package_mono_50.py` が `releases/mono-5.0.1/` と `FridayMono-5.0.1.zip` を作ります。
