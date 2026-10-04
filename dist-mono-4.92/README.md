# Friday Mono 4.92 / 2026-10-04

Windows Terminalで二重下線が一重に見えるバグを修正しました。
変換で選択中の文節とANSI二重下線に影響していた行の下側の余白を120から400 unitsへ拡大。
行高は1.00emから1.28emになります。Regularテスト版でWindows上の二重線と行間をユーザー確認済みです。

3ファミリ（Friday Mono / Friday Mono JP / Friday Mono Plain JP）、各Regular / Medium / Boldと各Italic。
計18 TTF、18 WOFF2。既存の正式書体名を維持しています。

4.91からの変更はhhea.descent、OS/2.sTypoDescender、版情報・説明とチェックサムのみです。
字形・文字幅・ヒント・文字収録・文字置換・位置調整・下線位置と太さは4.91と同一です。
保存後に変更対象以外の全テーブル・フィールドの完全一致を18書体で確認し、TTF/WOFF2も照合しました。
Terminalの計算式では全18書体、8–24pt・96/120/144/192 DPIの計1,224条件で二重線が分離します。
これは計算による予測です。全18書体をWindows実アプリで個別に再検証したという意味ではありません。
セル高のカスタム設定や別レンダラーはこの計算の対象外です。

## インストール

1. 使用するファミリのttf/内の書体をWindowsにインストール（4.91の置き換え）。
2. Windows Terminalを再起動し、Friday MonoまたはFriday Mono JPを選択します。
3. PowerShellで二重下線を確認します。

```powershell
$e = [char]27; Write-Host "${e}[4:2mABC クローン${e}[0m"
```

テスト版の「UL Test」とは別名です。日本語なしのFriday Monoは日本語を別フォントで表示します。
日本語入りはFriday Mono JP（斜線入り0）またはFriday Mono Plain JP（斜線なし0）です。

## 検証記録

reports/validation.jsonは今回の4.92の検査です。
reports/inherited-4.91/は4.91当時の検査記録で、今回のWindows全書体の確認結果ではありません。
文字収録・ゼロ切り替え・RC3修正内容は4.91から継承しています。

再ビルド：4.91の入力をbuild_mono_49.pyで用意し、build_mono_492.pyを実行します。
workspaceルートから `InoriMono-v3-build/.venv/bin/python FridayFonts/build_mono_492.py`。
