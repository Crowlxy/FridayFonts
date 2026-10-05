# Friday Mono 4.93 / 2026-10-06

4.92の各ファミリにLight（300）とSemiBold（600）を、直立とItalicの両方で追加しました。

3ファミリ（Friday Mono / Friday Mono JP / Friday Mono Plain JP）は、それぞれ次の10本です。

- Light / Regular / Medium / SemiBold / Bold
- 上の各Italic

計30 TTF、30 WOFF2です。

Regular / Medium / Boldの18本は4.92と同じ字形です。変更は版情報（headの版番号、名前ID 3 / 5 / 10）とチェックサムだけです。
保存後、それ以外の全テーブルと名前が4.92と完全一致することを確認しました。

## インストール

1. `ttf/` を開き、使うファミリの `.ttf` をすべて選ぶ
   - 日本語も表示するなら `FridayMonoJP-*`
   - 0の斜線が不要なら `FridayMonoPlainJP-*`
   - 英数字だけでよいなら `FridayMono-*`
2. 右クリックして「インストール」（Windows）、またはダブルクリックしてFont Bookで「インストール」（macOS）
3. アプリを再起動し、フォント名に `Friday Mono JP` などを指定する

4.92以前が入っている場合は、上書きしてかまいません。書体名は同じです。Webで使うときは `web/` のWOFF2と `friday-mono.css` を使います。
詳しい手順やアプリごとの設定は、[GitHubのREADME](https://github.com/Crowlxy/FridayFonts#インストール)を参照してください。

## Light / SemiBoldの作り方

R/M/Bを作ったのと同じ工程を、新しい2つのウェイトでもう一度通しました。

1. **欧文**：Iosevka Custom（34.8.1の構成）が元です。
   - Lightは既存のRegularから、SemiBoldは既存のMediumから作りました。輪郭を目標の線幅まで細らせ・太らせ、基準線・x-height・キャップ高・アセンダー・ディセンダーの上下位置は元の位置へ戻しています。
   - 目標の線幅は、R/M/Bと同じ基準（SF Monoの各ウェイトの線幅×補正値）で決めました。
   - Iosevkaの全ウェイトで同じ形の627字は、元の形のまま使います。ブロック要素、網掛け、Powerline、中心線などです。
   - 細らせると形が保てない記号は、元の形のまま使います。Lightでトランプ、装飾記号などの56字、Light Italicで101字です。
2. **和文**：Noto Sans CJK JPのwght軸の値を、漢字の線幅を測りながら決めました。手描きかなは、承認済みの手描き輪郭と同じ生成手順で、新しい線幅に合わせて作りました。
3. **仕上げ**：v47の工程を順に通しました。ttfautohint（数字の高さ揃え検査付き）、漢字ヒント（Chlorophytum）、v48の名前です。
4. **Windows対策とRC3**：Windows検証候補RC3の工程を、R/M/Bと同じ順に通しました。かなのヒント除去、濁音かなの本体の高さ、Winメトリクス、縦書きかな、記号ヒント、囲み記号、𠮷です。
5. **Italic**：RC3の方針をItalicに当て直しました。漢字の移動上限は、Italicの輪郭で独立に測っています。
6. **4.92の変更**：行の下側の余白を−400にしました。日本語なし版を作り、JPとPlain JPのゼロを切り替えています。どちらも4.92と同じスクリプトです。

旧式Windowsの4書体（RIBBI）互換のため、Light / SemiBoldのlegacy familyは「Friday Mono JP Light」などのウェイト名付きです。サブファミリーはRegularまたはItalicです。4.92のMediumと同じ方式です。

## 太さの統一

`reports/weight-audit.json`より、各ウェイトの線幅（1000 units）です。

| Friday Mono JP | Light | Regular | Medium | SemiBold | Bold |
|---|---:|---:|---:|---:|---:|
| 欧文 H の縦線 | 68 | 86 | 104 | 118 | 140 |
| 漢字の縦線（中央値） | 49 | 64 | 78.5 | 91.5 | 113 |
| かなの線（中央値） | 49.6 | 63.6 | 78.1 | 90.8 | 111.9 |

- 全ファミリ・直立とItalicの両方で、欧文・漢字・かなが細い順に揃っています。
- 漢字とかなの差は全ウェイトで約1.2 units以内です。
- 見本：`reports/weights-proof-*.png`、`reports/proof-new-weights.png`

## 検証

- **新しい12本**：4.91と同じ検査（`reports/validation-new-weights.json`）を通しました。
  - RC3の入力と輪郭・ヒント・字幅が一致すること
  - Plainはゼロだけが異なること
  - ゼロ切り替え機能と異体字シーケンス
  - 合成済み文字と分解表記の一致（420組／883組）
  - 日本語なし版の全グリフの小サイズ描画が入力と一致すること
- 行の高さに関わる数値（hhea・OS/2）で入力と違うのは、ディセンダーの−400だけであることを確認しました。
- **Italic**：Light Italic・SemiBold Italicの全グリフを、2方式・13サイズで描画しました。各535,626件でエラー0、12px以上の空描画0です。欧文はv48 Italicの描画と一致しました。結果は`reports/italic-render-audit.json`です。
- **全30本**：全グリフを9〜24px、2方式で描画し、エラー0・空描画0でした。
- 新しい12本は、4.92と同じWindows Terminalの計算式で、8〜24pt・4種のDPIのすべてで二重下線が分離します。
- TTFとWOFF2の輪郭・命令・テーブルの一致を確認しました。

## 残る事項

- **Light / SemiBoldはWindows実機で未確認です。**
- **新ウェイトの手描きかなは、ユーザーの目視承認を受けていません。** 承認済みの生成手順で作り、自動計測と見本で確認した段階です。
- **欧文はIosevka本来のLight / SemiBoldではありません。** Iosevkaのビルド（npm）を実行できなかったため、既存のRegular / Mediumから輪郭を細らせ・太らせて作りました。
  - 線幅と上下の位置はR/M/Bと同じ基準に合わせています。
  - 字の内側の空き（カウンター）の取り方は、Iosevka本来の別ウェイトと細部が異なる可能性があります。
- Lightの漢字の横線補正（−2.1 units）は、既存の仕組みで7,979字に適用しました。形が崩れると判定された1,853字は補正せず、元の形のままです。

## 再生成

プロジェクトルートから、`FridayFonts/scripts/weights/build_weights.py`の各工程（iosevka → mono-raw → mono-finish → mono-v48 → ws-*）を実行し、最後に次を実行します。

```sh
InoriMono-v3-build/.venv/bin/python FridayFonts/scripts/weights/release_mono.py
InoriMono-v3-build/.venv/bin/python FridayFonts/scripts/weights/verify_mono_weights.py
InoriMono-v3-build/.venv/bin/python FridayFonts/scripts/weights/audit_weights.py FridayFonts/releases/mono-4.93
```

フォントの利用・再配布条件は同梱の`OFL.txt`と`licenses/`を参照してください。
