# Codex へのレビュー依頼（指示文）

以下を Codex に渡してください。リポジトリのルート `C:\Users\hru00\Desktop\Project\Friday Fonts` で作業させます。

---

## あなたの役割

あなたは Friday Fonts（Friday Sans / Sans UI / Friday Mono）の**独立したレビュー役**です。別の AI（Claude）が 2026-10-10 に行った修正を検証し、あわせてフォント全体を監査して、問題を見つけて報告してください。**Claude の記録（README・レビュー結果.md・reviews/）は主張であって証拠ではありません。** 自分で測り、再現できなかったものは「再現できなかった」と書いてください。

## してはいけないこと

- フォント・スクリプト・文書・Release を**変更しない**（`AGENTS.md`：レビューはユーザーの依頼があるときだけ。今回は依頼済み）。出力は `reviews/codex-<日付>.md` と `work/codex-review/` だけ。
- 公開（GitHub Release・タグ・資産の差し替え・push）をしない。git commit もしない。
- `work/` の既存ファイル（Claude のビルド出力）を上書き・削除しない。再ビルドは `work/codex-review/` に出力する。
- 著作権のある参照フォント（`reference/` の SF・ヒラギノ）を出力に含めない。測定にだけ使う。

## 背景（事実）

- 公開済み：Sans `sans-v3.0`（内部版 3.000、密度対応前）、Mono `mono-v5.0.1`。
- 2026-10-09 に Claude がレビュー r3（`reviews/2026-10-09-r3.md`）を行い、Sans Light の漢字が壊れている（2.5 から継続）、Mono Light が細すぎる、などを指摘。一覧は `レビュー結果.md`。
- 2026-10-10 に Claude が修正（記録：`reviews/2026-10-10-fixes.md`）。**変更は未コミット**（`git status` で確認）。`git mv` の移動だけがステージ済み。
- 成果物（手元のみ、未公開）：`FridaySans-3.002.zip`（SHA-256 `0d1af9ce…`）、`FridayMono-5.0.3.zip`（`29602551…`、**ユーザー承認前の候補**）。展開済みフォントは `work/sans-3.0/ttf/`（Sans 10 本）、`work/mono-5.0/ttf/`（Mono 10 本）。
- 入力：Sans は公開済み `FridaySans-2.5.zip`（`work/sans-3.0/x/FridaySans-2.5/ttf/`）、Mono は `FridayMono-4.93.zip`（ルート直下）。元のビルド環境（Source/ など）はこの PC に無く、**Claude は公開済み ZIP から作り直した**。3.001 の手元 ZIP は存在せず、`work/sans-3.0/ttf-base/`（3.001 相当を作り直したもの）で代用した。
- 環境：フォントツールは `.venv`（`docs/FONT-TOOLS.md`、`scripts/activate-font-tools.ps1`）。ビルド用 Python は `work/venv`（`scripts/requirements-v47.txt`）。Python は `-I -X utf8` で実行する。

## 依頼の範囲（2 部構成）

### A. 今回の修正の検証

下の表の各主張について、**独立に再測定**して合否を判定してください。方法は Claude の検査スクリプトを再利用してもよいが、**同じ検査の再実行だけで合格としない**（検査の盲点が疑われるため、別の方法でも 1 つは確かめる）。

| # | Claude の主張 | 確かめること |
|---|---|---|
| A1 | Sans Light の壊れた漢字 95 字（`scripts/sans30/light_repair.json`）を Regular から作り直し、壊れは無くなった | (1) 95 字を自分で目視（Light / Regular / Medium を並べる）。作り直した字が**別の欠陥**（細りすぎ、払いの先の消失、はみ出し、重心のずれ）を持たないか。(2) `light_repair.json` に**入っていない**壊れた字がないか。`xweight.py` は 160 px/em・8 px² 以上のかたまりしか見ない。閾値以下、**全ウェイトで同じ壊れ**、Light 以外の壊れ（Regular〜Bold、UI、cmap にない異体字）は盲点。Noto Sans JP（`reference/Noto_Sans_JP/static/`）の Light・Regular との**独立した比較**を推奨 |
| A2 | 太さの段差が潰れていた漢字を `ladder_pass` で直した（全ペアで、2.5 の段差の 50 % 未満の字が 0） | 50 % という基準が妥当か。軽い側を**減らして**直したので、Light・Regular・Medium の密な漢字が 2.5 並みに薄くなっていないか（Sans の密な漢字：鬱・龍・議・響・齟・辯 など、3.001 相当との面積差と目視）。2.5 の段差そのものが元から小さい字の扱い |
| A3 | 0.5 unit 以内で接する輪郭の融合を許して、太らせを受けなかった字を減らした（`widen` の `n1`） | 融合した字（Sans 書体ごとに 5〜19 字）で、**見た目の隙間が埋まっていないか**（`work/sans-3.0/verify.json` の `fused`）。新しい小片（ゴミ）が出ていないか |
| A4 | ≒（U+2252）を追加した（`scripts/sans30/fixups.py`） | 字形の妥当性（日本の字形：左上の点・右下の点）、5 ウェイトでの線・点の太さの整合、UI の幅、`vert` の要否、縦組み時の位置、cmap・hmtx・vmtx・GSUB への影響、WOFF2 軽量版に入っていること。**この字形は Claude が作ったもので、ユーザーの目視承認を受けていない** |
| A5 | Bold の ℊ（U+210A）を 214 units 下げた | SemiBold と並べて妥当か。ほかにも Bold だけ違う字（ℏ U+210F・∊ U+220A の幅など）がないか |
| A6 | 結合記号の送り幅を Light に合わせて 0 にし、ゼロ幅の結合記号 40 字を GDEF の mark クラスに入れた | PUA の `…comb` 字形が cmap・GSUB（ccmp など）でどう使われるか。**HarfBuzz は mark クラスの字の送りを 0 にする**ので、意図しない字が mark になっていないか。`scripts/qa/shape_regress.py` の見本文には結合記号が入っていない（Claude が別に確認した）。GDEF 変更前後で、実際のテキスト（ベトナム語、ウムラウト、合成分音、ルビ）の組版が変わらないか |
| A7 | Mac 用 name レコードと ltag を外した | Sans・Mono の両方で、既存アプリ（Word for Mac、古い Adobe 製品、Windows の古い GDI アプリ）で**ファミリー名・スタイル名の解決が変わらないか**。nameID 1/2/4/6/16/17 が Windows レコードに揃っているか |
| A8 | Mono Light・LightItalic を +5 units 太らせた（62→66）。ほかの 8 スタイルの座標は 5.0 と同一 | (1) 8 スタイルの座標・送り幅・cmap・グリフ順が `FridayMono-5.0.zip`（GitHub の mono-v5.0 / v5.0.1）と同一か（違うのは hinting・name・head・FeatureParams だけ）。(2) Light の字形（B・e・X・&・§・Ǫ・数字・記号・罫線）に新しい欠陥がないか。針状の点の除去（`light_stem.trim_needles`）が正しい点を取ったか。(3) FontForge で Light の**自己交差が増えた**（Light 24→31、LightItalic は 59→37）が、描画上の問題になるか（ClearType・FreeType・Skia）。(4) 線の太さの段差（62→66→80→92→104→123）が妥当か。+6・+7 で ttfautohint の数字桁そろえが失敗する原因（Claude は未調査） |
| A9 | `head.flags` ビット 3、Mono の Mac 名・name 末尾の空白の除去、ss01・cv01 の FeatureParams を全 10 スタイルに入れた | 既に承認済みのウェイト（Regular〜Bold）の**描画が変わっていないか**（FreeType の整数 ppem 丸め、DirectWrite、CoreText）。FeatureParams の名前（"Zero without slash"）が実際の ss01・cv01 の字形（zero と zero.alt）と合っているか |
| A10 | WOFF2 は Chromium・Firefox・WebKit で読み込め、描画できる。HarfBuzz の組版は 3.001 相当と不一致 0、Mono は 5.0 と不一致 0 | OTS（`ots-sanitize`、導入されていれば）での検証。Claude は**読み込み成功**と見本の PNG しか確認していない。実際の描画がフォールバックでないことを、グリフの形で確かめる（Claude の `browser_check.py` は `document.fonts` の状態しか見ない） |
| A11 | Sans の Fontspector の残る FAIL は設計判断（`vert`+`vrt2`、10〜11 MB、`case_mapping`、ファミリー間比較） | 本当に許容できるか。特に `vert` と `vrt2` の併存（Noto CJK も併存）と、GSUB の `vrt2` の中身 |

### B. フォント全体の監査（今回の修正に限らない）

**出荷版としての品質を、自分の観点で洗い出してください。** 以下は優先順位つきの観点です（見つけた順に報告）。

1. **字形の壊れ**（最優先）。Sans・Sans UI の全 10 書体 × 全字形（約 16,759）、Mono の全 10 スタイル × 全字形（1,251）。ウェイト間・UI↔Sans・Italic↔Upright・Noto Sans JP / Inter / Iosevka 由来の元との比較、ラスタ差・輪郭の自己交差・微小な輪郭・開いた輪郭・向き・極値の欠け・極端な点間隔。**検査が見ない領域**（Claude の xweight は全幅の漢字・かなだけ）：欧文 Latin（Inter 由来）の 5 ウェイト、ギリシャ・キリル、記号・約物・罫線、半角カナ、縦書き形（`vert`）、異体字（cmap にない `jp.*` 字形）、手描きかな（ぶ・ふ・ぷ・小書きかな）。
2. **ウェイトの整合**。線の太さの階段（Sans：漢字・かな・欧文の縦横線）、x 高さ・大文字の高さ・基線のずれ、字幅（比例幅のウェイト間のジャンプ：Bold の ℏ・∊ のような）、Mono のウェイト間の段差と ½・¼ など。
3. **小サイズでの見え**（9〜24 px）。ヒントなしの Sans（3.0 は意図的にヒントを外している）と、ヒント付き Mono。FreeType（`PIL`）、DirectWrite 相当（Playwright の Chromium）、Windows GDI（`scripts/mono50/windows/*.ps1`）で、字の欠け・つぶれ・位相による濃さのゆれ。**ClearType の実画面は Claude は未確認**。可能なら Windows で ClearType を有効にして Light・SemiBold を確認し、「未確認」を埋める。
4. **メトリクス・OS/2・name・cmap・GSUB・GPOS・GDEF・post・head・hhea・vhea・vmtx**：換算漏れ、ファミリー内の整合、Win 値（Sans は 1.87 em。〱〲 が原因。**判断はユーザー**）、行の高さ、usWin が全字形を覆うか、fsType・ライセンス・ベンダー ID・バージョン文字列、PostScript 名の一意性、`OFL.txt`・`licenses/` の整合、フォントの重複 name ID、Mac/Windows 間の食い違い。
5. **OpenType 機能**：`palt` `halt` `vert` `vrt2` `jp78` `jp90` `fwid` `hwid` `ruby` `tnum` `zero` `ss01`〜`ss08` `cv01`〜`cv14` `case` `kern` `liga` `calt` の動作を、日本語・ラテンの代表的な文字列で（HarfBuzz、`hb-shape`）。Claude は 3.001 相当との**差分**しか見ていないので、**そもそも壊れている機能**は拾えていない（例：UI のかな詰め、Sans の `palt` 未対応は README に既知）。
6. **文字セット**：JIS X 0208・X 0213、人名用漢字、常用漢字表、IVS（`cmap` format 14）、半角カナ、全角記号。Sans に無い JIS X 0208 の字（≒ は追加済み。ほかにないか）。2.5 から欠けている字の有無。
7. **配布物**：ZIP の中身とハッシュ（`SHA256SUMS.txt`）、READMEの記述と実測の一致（**README の数値を実測で 5 つ以上確かめる**）、`font-manifest.json`、`build-log.json`、`.gitignore`、docs の再現手順がこの PC で最後まで通るか（`docs/BUILDING.md` の Sans 3.002 の順序、Mono の `MONO_LIGHT_GROW=5`）。
8. **再現性**：`work/codex-review/` に Sans 3.002 を作り直し（約 35 分）、ZIP のフォントとグリフ単位で一致するか（TTF のバイト一致は日時で崩れるので、cmap・全字形の座標・hmtx・name を比較）。Mono 5.0.3 も同様。

### Claude が自覚している弱点（重点的に疑ってください）

- Light の作り直しは「Regular の輪郭を内側へオフセットして Light の面積に合わせる」方式で、**元の Noto Sans CJK JP の Light ではない**。払いの先・うろこ・ハネの細さが、他の（Noto 由来の）Light の字と違って見える可能性がある。元のソース（Noto Sans CJK JP の可変軸）は再現していない。
- 壊れの**原因は未特定**。同じ原因の壊れが、閾値（8→2 px²）より小さい形で、あるいは Light 以外・UI 固有・異体字に残っているかもしれない。
- `xweight.py` は、全幅のグリフにだけ働く（ラテンの比例幅は対象外）。Latin Light の欠陥は見ていない。
- `ladder_pass` の基準 50 % と、`+0.05` の狙い値は経験的な値。
- `n1`（融合を許す基準）は、新しい小片を許さない（`min(n0, n1)`）が、**融合が妥当かの自動判定はない**。
- ≒ は Claude の自作。点の径（線の 1.45 倍）と位置（線の 0.55 倍の隙間）は経験的。
- GDEF の mark クラス化は `unicodedata`・`…comb` 名・幅 0・輪郭ありの条件。**意図しない字を含む可能性**。
- Mono の +5 は「ttfautohint が通る上限」で決めており、**見た目の最適**ではない（ユーザー承認は未）。Light の自己交差 7 字は未目視。
- 3.001 の実物が無く、3.001 相当との比較は「再現した別ビルド」との比較。
- 検査の再実行は `verify_sans_30.py` が約 25 分かかる。
- WOFF2 の検証は「読み込み成功」まで。OTS 未実施。
- ClearType・macOS・iOS・Android は未確認。

## 作業の進め方

1. `git status`・`git diff --stat`・`reviews/2026-10-10-fixes.md` を読み、変更範囲をつかむ（読むだけ。スクリプトの実行は A・B の検証のため）。
2. A の各主張を、方法を変えて検証する。壊れを見つけたら、**字・ウェイト・数値・画像（`work/codex-review/*.png`）**を添えて報告する。
3. B の監査は、1（字形の壊れ）→ 2（ウェイト）→ 4（メトリクス）→ 3（小サイズ）→ 5（機能）→ 6（文字セット）→ 7（配布物）→ 8（再現性）の順。時間が足りなければ、**やらなかった項目を明示**する。
4. 同じ検査を二度書かない。既知の問題（`レビュー結果.md` の #5・#20・#21、README の「残る事項」）は再掲せず、**新規の発見**と、**既知の問題の深刻度の再評価**に集中する。

## 出力

`reviews/codex-<日付>.md` に、次の形式で書いてください（日本語。ほかのレビュー文書 `reviews/2026-10-09-r3.md` の形式に合わせる）。

1. **判定**：3.002 を公開してよいか（可／条件つき／不可）、Mono 5.0.3 を承認に回してよいか。理由を 3 行で。
2. **指摘**（重大度順）。各指摘に：`[P0〜P3]`、対象（ファイル・ウェイト・字）、症状、**再現方法**（コマンドかスクリプト、画像）、根拠（測定値）、修正案、確かさ（確認済み／推定）。
   - P0：出荷を止める（字形の壊れ、名前・メトリクスで読み込めない、ライセンス）
   - P1：公開前に直す（Light・SemiBold の見え、機能の誤動作）
   - P2：直したほうがよい（整合、文書）
   - P3：記録しておく
3. **Claude の主張の検証結果**（A1〜A11 の各行に：再現／再現せず／検証せず、と一言）。
4. **検査していないこと**と、その理由（時間、環境、権限）。
5. **再現手順**：使ったコマンドとスクリプトの場所（`work/codex-review/`）。

**書いてはいけないこと**：確認していないことを「問題なし」と書く。見ていない字を「正常」と書く。数値だけで外観を承認する（外観の承認はユーザーの目視が必要。**「ClearType 実機は未確認」は必ず明記**）。

---

## 依頼者（ユーザー）側の補足

- Claude の記録は `レビュー結果.md`（一覧）、`reviews/2026-10-10-fixes.md`（対応）、`releases/sans-3.0/README.md`・`releases/mono-5.0.3/README.md`（成果物の説明）。
- Sans の既知の設計判断：ヒントを外している（3.0）、行の高さ 1.87 em（〱〲）。変更の依頼ではなく、**評価**を求める。
- 問題が見つかったら、**ファイルを直さずに**報告だけしてください。直すかどうかはこちらで決めます。
