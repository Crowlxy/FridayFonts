# Friday Sans 2.5 / Friday Sans UI 2.5

Windows検証候補RC3（WinProof Sans RC3 / WinProof Sans UI RC3）を正式名に戻して現行版にしました。
あわせてLight（300）とSemiBold（600）を追加し、各5ウェイトになりました。

| ファミリー | ウェイト | 用途 |
|---|---|---|
| Friday Sans | Light / Regular / Medium / SemiBold / Bold | 本文 |
| Friday Sans UI | Light / Regular / Medium / SemiBold / Bold | 画面の文字。字面を約5%小さくし、かなと約物の幅を詰めた版 |

計10 TTF、10 WOFF2。内部バージョンはVersion 2.500です。

## 2.1・RC3からの変更

- Regular / Medium / BoldはRC3のファイルが元です。変更は次の2点だけで、それ以外の全テーブルがRC3と完全一致することを確認しました。
  - 名前テーブル（ファミリー名・版・説明）とheadの版番号
  - Friday SansのMedium・Boldで「ぶ・ぷ」の送り幅を直しました。1.1から、手描きの点が枠の左端を数単位越えたため、記号用の幅の計算（字の幅＋100）が誤って使われ、1064〜1083になっていました。横書き・縦書きの字を元の位置に戻して送り幅を1000にし、中心に付くマーク位置も同じ量だけ戻しました。変更は4字（横・縦×ぶ・ぷ）と、そのマーク位置2か所だけです。Sans UIは独自の幅を持つため影響はありません。
- Light / SemiBoldは、Regular / Medium / Boldを作ったのと同じ工程を、2つのウェイトでもう一度通して作りました。
  1. 欧文はInter 4.1のwght / opsz軸から作りました。線幅と字面の高さがR/M/Bの間に入る値を求めています。
  2. 和文はNoto Sans CJK JPから、同じ方法で作りました。漢字の線幅を測りながら軸の値を決めています。
  3. 手描きかなは、承認済みの手描き輪郭を作るのと同じスクリプトで、新しい線幅に合わせて生成しました。
  4. 欧文・和文を合成し、ttfautohintと漢字ヒント（Chlorophytum）を付けました。
  5. 2.0・2.1の修正（合成半濁点14組、𠮷、結合濁点の配置）を入れました。
  6. Windows対策を入れました。漢字の大きな変形を抑えるガード、濁音・半濁音かなの本体の高さの修正、UI版の調整です。
  7. RC1〜RC3の修正を入れました。Winメトリクス、縦書きかな、記号ヒント、囲み記号の配置です。
- 旧式Windowsの4書体（RIBBI）互換のため、Light / Medium / SemiBoldのlegacy familyは「Friday Sans Light」などのウェイト名付き、サブファミリーはRegularです。
- 新しいアプリはtypographic family（Friday Sans）とウェイトで選ばれます。

## 太さの統一

`reports/weight-audit.json`に、各ウェイトの線幅を記録しています（1000 units換算）。

| Friday Sans | Light | Regular | Medium | SemiBold | Bold |
|---|---:|---:|---:|---:|---:|
| 欧文 n の縦線 | 57 | 75 | 90 | 101 | 116 |
| 漢字の縦線（中央値） | 49 | 64 | 78.5 | 87 | 100 |
| かなの線（中央値） | 50.2 | 64.2 | 78.5 | 86.8 | 99.9 |

- 漢字とかなの線幅は、全ウェイトで約1.2 units以内に揃っています。
- 手描きかな（あ・き・さ・と・ふ・や など）の線は、周りのかなとの比が0.85〜1.04です。新ウェイトの値はR/M/Bの範囲内です。
- UI版も同じ順に太くなります。
- 見本：`reports/weights-proof-FridaySans.png`、`reports/weights-proof-FridaySansUI.png`

## 検証

- 全10書体の全グリフをFreeTypeで描画しました。条件は9〜24px、ヒント方式2種（v35 / v40）です。描画エラー0、輪郭のあるグリフの空描画0でした。
- Light / SemiBoldは、R/M/Bと同じ漢字ガード・濁音かなの検査を通しました。
  - 内容：全グリフ描画、ヒントによる点の移動上限、形状、メトリクス、マーク位置、混植の組版。
  - 計1,407,672件で失敗0でした。
- 行の高さに関わる数値（Winメトリクス、hhea、OS/2 typo）と、グリフ数・収録文字数（16,758 / 15,233）は、R/M/Bと一致しています。
- TTFとWOFF2の輪郭とテーブルの一致を確認しました。

## 残る事項

- **Light / SemiBoldはWindows実機で未確認です。** RC3のWindows検証（WPF・WinUI・Edge・GDI）はRegular / Medium / Boldが対象でした。
- **新ウェイトの手描きかなは、ユーザーの目視承認を受けていません。** 承認済みの生成手順で作り、自動計測と見本で確認した段階です。
- Medium・Boldの「ぶ・ぷ」の修正は、Windows実機での確認がまだです。修正前のRC3はWindows確認済みです。
- RC3の報告にある制限（旧GDIの自動行間が広がる、小サイズの細い複雑記号）は全ウェイトに共通です。

## 再生成

プロジェクトルートから、`FridayFonts/weights/build_weights.py`の各工程（sans-cjk → sans-unity → sans-20 → sans-21 → ws-*）を実行し、最後に次を実行します。

```sh
InoriMono-v3-build/.venv/bin/python FridayFonts/weights/release_sans.py
InoriMono-v3-build/.venv/bin/python FridayFonts/weights/audit_weights.py FridayFonts/sans/dist-2.5
```

フォントの利用・再配布条件は同梱`OFL.txt`と`licenses/`を参照してください。
