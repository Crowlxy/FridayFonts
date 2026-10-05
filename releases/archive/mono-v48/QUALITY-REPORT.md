# Friday Mono v48 品質調査

v48 は v47（旧名 Inori Mono）の名称変更版です。輪郭・字幅・ヒント・OpenType 機能は v47 とバイト単位で同一であることを `rename_v48.py` が確認しています。
そのため以下は v47 の調査をそのまま収録しています（ファイル名・書体名は旧名のまま）。機械検査の生データは `audit/v47/` にあります。

v47 の Windows（WPF）実機確認：12 本すべて読み込み・描画に成功。Regular 12/16/20px で仮名・漢字の上端の残差は最大 1px（濁点付きの字が設計上 0.6〜0.9px 高いぶん）。GDI と個別エディタは未検証。

---

# Inori Mono v47 配布前品質調査

2026-10-01。最終TTFは **Version 4.700 / head.fontRevision 4.700**。
Inori Mono / Inori Mono Plain、各Regular・Medium・Bold × 正体・Italicの計12本。
1本あたり **20,600グリフ・19,311コードポイント**。

**v47の変更はTrueTypeヒントだけです。輪郭・字幅・レイアウト・欧文のヒントはv46と同一です。実行した技術検査は合格しました。Windows実機とSafariの最終表示は未検証です。**

## 修正内容

|項目|v46で確認した問題|v47の対応|
|---|---|---|
|仮名・漢字のヒント|ttfautohintにCJK用の設定がなく、仮名・漢字の上端・下端が1字ずつ独立に丸められていた。Windowsのエディタ等で、濁点付きの仮名（が・で・ぽ・ヴ）や一部の漢字（信・君）が1〜2px上下にはみ出し、1字だけ大きく見えた|ttfautohintの後に `cjkhint.py` でChlorophytum（Sarasa Gothicのヒンター）の表意文字ヒントを追加。仮名・漢字を共通の字面枠へ揃える|
|FreeTypeでの表示|—|Chlorophytumの字面枠用の点がFreeTypeの安全上限を越えると漢字が潰れるため、cvtに未使用の0を足して上限を確保|
|Web読み込み|—|Chlorophytumの出力はOTS（Chrome / Firefoxの検査器）が拒否するグリフフラグを含むため、ヒント命令だけを元のフォントへ移植|

同じ設計高さの仮名・漢字のうち、多数派と違う画素行に丸められる字の割合（FreeType、11〜24px）：

|ウェイト|v46|v47|
|---|---:|---:|
|Regular / Italic|22.3% / 21.9%|2.5% / 2.5%|
|Medium / MediumItalic|24.4% / 24.5%|2.8% / 2.8%|
|Bold / BoldItalic|24.7% / 24.7%|4.7% / 4.7%|

Plainは同じ値です。輪郭のぼやけ（中間調の割合）はRegularで48.3→43.0とむしろ減っています。
欧文のヒント命令が変わったグリフは12本すべてで0。v46のfpgm・prep・cvtはそのまま先頭に残し、Chlorophytumはその後ろへ追加しています。

## 検証結果

|検査|結果・範囲|
|---|---|
|ビルド回帰テスト|9/9合格|
|v46との差分|全12本で輪郭座標・フラグ・輪郭構成の差0。差のあるテーブルはヒント（fpgm / prep / cvt / maxp / 各グリフの命令）とname / headだけ|
|既存詳細検査|validate.py：12/12合格|
|承認済み独自仮名|11字×12本＝132字の輪郭座標・輪郭構成が一致|
|全グリフ数値検査|全12本の20,600グリフで描画例外0、Windowsクリップ範囲超過0。太さ間の寸法差候補は28件（18文字）でv46と同数|
|HarfBuzz・異体字|全19,311コードポイントで.notdefなし。883種の正規化済み文字とNFD文字列が同一の組版結果。11,502件の異体字参照整合|
|文字コード|Windows-1252/1250/1251/1253/1254/1257、CP932、Shift_JIS-2004の標準文字で欠落0|
|TrueTypeヒント|数字の小サイズ整列：12本すべて合格。仮名・漢字10,769字×12本を12 / 16 / 20pxで描画し、潰れ0。OTSが拒否するグリフフラグ0|
|FreeType実描画|16pxで全収録コードポイント×12本＝231,732件。描画例外・意図しない空表示0|
|Mac CoreText|12本をプロセス内登録し、実描画。代表文字のフォールバック0。NFC/NFD、結合文字、ZWJの幅を確認|
|Chromium 152|TTF12本＋WOFF2 12本＝24/24合格（OTSによる読み込み拒否なし）。CSSによる12スタイル選択、欧文・和文幅、結合文字・不可視文字の幅を確認|
|WOFF2往復|再展開後のcmap・hmtx一致、GSUB/GPOS/GDEF/name/OS2/vmtx一致、全グリフの座標・輪郭構成一致|
|通常版 / Plain版|コードポイント別の境界・面積・輪郭数・送り幅の差は数字0だけ|

## 未確認の環境・適用範囲

- WindowsのGDI / DirectWriteでの実表示は未検証です。ヒントの効果はFreeTypeのTrueTypeインタプリタで測定しました。Windowsはこのヒントを使うため同じ方向の改善が見込めますが、実機での確認が必要です。
- Safari、Firefox、iOS、Androidは実機検証済みとはしていません。Web実測はChromium 152です。
- macOSはTrueTypeヒントを使わないため、v46と表示は変わりません。
- v46の調査報告に記載した対応範囲・ライセンス・配布内容の条件は変わりません。

## 証拠

`release-audit.json`、`encoding-audit.json`、`raster-audit.json`、`coretext-audit.json`、`browser-audit.json`、
`metrics.json`、`all-metrics.json`、`coretext-preview.png`、`kana-latin-*.png`、`candidates-1.png`。
ビルドと再実行方法は `../BUILD-v47.md`。配布時にはZIPのCRCと同梱チェックサムを検証します。
