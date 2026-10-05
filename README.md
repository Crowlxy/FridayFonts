# Friday Fonts

コーディング用の等幅書体と、日本語の本文・UI用の書体。SIL Open Font License 1.1です。

## ダウンロード

| 書体 | 現行版 | 内容 | ダウンロード |
|---|---|---|---|
| **Friday Mono** | 4.93 | 日本語なし、1,088文字 | Mono 4.93（公開準備中） |
| **Friday Mono JP** | 4.93 | 日本語入り、19,312文字、斜線入り0 | 同じMono 4.93 ZIP |
| **Friday Mono Plain JP** | 4.93 | JPとゼロ関係だけ異なる、斜線なし0 | 同じMono 4.93 ZIP |
| **Friday Sans** | 2.5 | Inter + Noto Sans CJK JP + 手描きかな、本文用 | Sans 2.5（公開準備中） |
| **Friday Sans UI** | 2.5 | Friday Sansを画面の文字向けに調整 | 同じSans 2.5 ZIP |

Monoは3ファミリ × Light / Regular / Medium / SemiBold / Boldと各Italic、計30本。日本語なし版のPlainはありません。
Sans・Sans UIは各Light / Regular / Medium / SemiBold / Boldの計10本です。各ZIPにTTF・WOFF2・ライセンス・検査記録を同梱します。
旧版は[Releases](https://github.com/Crowlxy/FridayFonts/releases)に保存しています。

旧Friday Mono 4.8以前は日本語入りです。4.91で同じ書体を選ぶ場合は、アプリの指定を **Friday Mono JP** に変更してください。

## Mono 4.93 / Sans 2.5

全書体にLight（300）とSemiBold（600）を追加しました。MonoはItalicも含みます。
Sans・Sans UIは、Windows検証候補RC3（WinProof Sans RC3 / WinProof Sans UI RC3）を正式名に戻して現行版にしました。

既存のRegular / Medium / Boldは字形を変えていません。Monoは4.92、SansはRC3と同じです。
新しいウェイトは、既存のウェイトと同じ工程（欧文・和文・手描きかな・ヒント・Windows対策・RC3修正）で作りました。
線の太さは、欧文・漢字・かなとも全5段階で細い順に揃えています。

Light / SemiBoldはWindows実機で未確認です。新ウェイトの手描きかなも、まだ目視承認を受けていません。

- Mono 4.93：[変更・検証・残る事項](dist-mono-4.93/README.md)
- Sans 2.5：[変更・検証・残る事項](sans/dist-2.5/README.md)
- 作成スクリプト：[weights/](weights/)

## Mono 4.92

Windows Terminalで、IMEの選択文節やANSI二重下線が一重に見えるバグを修正しました。行の下側の余白を120から400 unitsへ増やし、行高を1.00emから1.28emに変更しています。Regularテスト版で二重線と行間をWindows上でユーザー確認済みです。

全18書体に同じ修正を適用しました。4.91との差分は行の下側の余白と版情報・説明・チェックサムだけです。字形・文字幅・ヒント・収録文字・GSUB/GPOS・下線位置と太さは完全一致しています。

全18書体のTTF/WOFF2を照合し、Terminalの計算式では計1,224条件で二重線が分離することを確認しました。全18書体をWindowsの実アプリで個別に再検証したという意味ではありません。

[変更と使い方](dist-mono-4.92/README.md) · [差分検査](dist-mono-4.92/reports/validation.json) · [作成スクリプト](build_mono_492.py)

### 4.91から継承した内容と検査記録

RC3のかな・縦書き・記号・囲み記号の修正と「𠮷」を反映し、Italicにも同じ修正方針を適用しました。
Italic専用の欧文字形・ヒントとCVT/prepを維持し、漢字の移動上限をItalicの輪郭で独立に測定しています。
JPとPlain JPはゼロ関係だけが違います。日本語なし版の文字範囲は、OTF等幅5書体の実ファイルを比較して決めました。

FreeType / HarfBuzzで派生18本を検査し、Italic全字形の1,606,878描画でエラー0件。
4.91のWindows実アプリでの確認はこれから行う段階なので、プレリリースとして配布します。

- [収録方針・使い方・検査範囲](dist-mono-4.91/README.md)
- [字形の比較見本](dist-mono-4.91/reports/proof.png)
- [派生フォント検査](dist-mono-4.91/reports/validation.json)
- [Italic全字形描画検査](dist-mono-4.91/reports/italic-render-audit.json)
- [キャッシュ速度測定](dist-mono-4.91/reports/cache-benchmark.json)

## Sans 2.1（旧版）

結合濁点・半濁点の合成と配置、「𠮷」とIVSを修正した版です。
[変更と検査範囲](sans/dist-2.1/README.md)。Windows実アプリでの確認が残るため、こちらもプレリリースです。
[漢字ヒント試作](sans/grid-trial-2.1/README.md)・[かな試作2.2](sans/kana-trial-2.2/README.md)は別の比較候補です。

## ソースとビルド

このリポジトリにはソース、設計資料、ライセンスと検査記録を保存しています。
TTF・WOFF2・配布ZIP・フォント内蔵比較HTMLはReleasesに集約しています。ローカルの生成物はGitの管理対象外です。

ローカルの研究workspaceからのMonoビルド:

```sh
InoriMono-v3-build/.venv/bin/python FridayFonts/build_mono_49.py
InoriMono-v3-build/.venv/bin/python FridayFonts/verify_mono_49.py
InoriMono-v3-build/.venv/bin/python FridayFonts/audit_italic_rc3.py
InoriMono-v3-build/.venv/bin/python FridayFonts/package_mono_49.py
InoriMono-v3-build/.venv/bin/python FridayFonts/build_mono_492.py
```

現在のスクリプトは、隣接するSource・comparisons・FridayFonts-WindowsTestと保存済み入力フォントを使用します。
このリポジトリ単体のcloneだけで再ビルドできる構成にはなっていません。

入力・コード・設定・ツール版のハッシュを使う工程キャッシュは `.build-cache/mono/` に保存します。
キャッシュ内の出力ハッシュを確認し、変更した工程だけ再作成します。`--no-cache`で再利用を無効化できます。
同一入力の再実行は約0.43秒でした。描画監査とZIP作成を含めた時間ではありません。

## 設計とライセンス

[設計資料](DESIGN.md) · [OFL](OFL.txt) · [旧Mono v48の説明](RELEASE-v48.md)

欧文はIosevka（Mono）／Inter（Sans）、和文はNoto Sans CJK JPと手描きかなです。
SF Mono・SF Pro・ヒラギノからは設計のための数値を測定しており、それらの字形データは生成フォントへコピーしていません。
参照した独自ライセンスのフォント自体は配布物に含めません。
