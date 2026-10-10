# Friday Fonts 独立レビューと修正（2026-10-10）

対象：Friday Sans / Sans UI 3.002、Friday Mono 5.0.3 候補。既存の未コミット変更を保持し、公開・コミットはしていない。依頼文の「報告のみ」は、今回のユーザーの「問題を記録して修正」という指示で更新されたものとして作業した。

## 判定

**Sans 3.002：条件つき。Mono 5.0.3：目視承認に回してよいが、公開は条件つき。**
今回確認した範囲で新たな出荷停止級の字形破損は確認していない。検査の偽合格、見本の不足、依存・説明の不備は修正した。
**ClearType 実機は未確認**。Light／SemiBold、≒、手描きかなの外観承認と、Macの実アプリ確認は自動検査からは代行できない。

本書の「問題を確認していない」は、全字形の外観を承認したという意味ではない。修復95字・融合候補・独立比較の上位候補を目視し、それ以外には機械検査の限界が残る。

## 指摘と対応

### [P1・修正済み] ブラウザ検査が Italic とフォールバックを検証していなかった

- 対象：`scripts/qa/browser_check.py`。
- 症状：Italic 行に `font-style:italic` がなく、結果をウェイトだけで保存すると直立／Italicが上書きされる。`document.fonts` の状態しか調べず、face 0 件でも成功しうる。旧コードの実行結果だけでは字形の実描画を保証できない。
- 修正：スタイルごとに正規のCSS・結果キーを使用。face 1 件のロード・インクの存在・Canvas画像のフォールバックとの差を要求。文字別の画像差も保存し、全体の成功と一部文字のフォールバックを区別した。不正なスタイルも拒否する。
- 再現・根拠：`work/codex-review/browser/notes.md`、`negative/results.json`、`browser-*.json`。全字形版／軽量版／Monoの合計90 face×engineで成功。異常系8試験が成功し、face 0で別フォールバックにより画素差が出ても不合格となる。
- 軽量版の「隄」U+9684はフォールバック。文字集合の対象外であり全字形版では対象フォントを描画する。≒は全字形版・軽量版の全ウェイト・全エンジンで個別画像差を確認。
- 確かさ：確認済み。読み込み・代表字形の描画を検証するもので、全字形の見えを保証しない。

### [P1・修正済み] 組版回帰検査が例外・比較漏れを成功と扱う

- 対象：`scripts/qa/shape_regress.py`。例外をERRとして表示しても失敗数へ足さず、片側のフォント不在・比較0件も成功する。
- 修正：例外・片側不在・比較0件を不合格にした。結合Latin／ベトナム語／かなの2見本を加え、許容誤差は縦組みのyオフセットだけに限定。フォントと字形順は上限20のキャッシュにし、同じ巨大TTFの繰り返し読込みを削減。
- 根拠：`browser/shape-negative/results.json`（7試験成功）、`shape-sans.log`（4,400組版、差0・例外0）、`shape-mono-tol0.log`（4,400組版、縦オフセット差242件）、`shape-mono-tol2.log`（縦yオフセットのみ2units許容で差0・例外0）。実測最大差は2unitsで、Light／LightItalicだけ。ほかの8スタイルは厳密一致。Monoの水平送り・字形列・縦送り・xオフセットも全スタイルで厳密一致。
- 確かさ：確認済み。既存の不一致0という結果だけで検査が健全と判断せず、失敗ケースも実行した。

### [P2・修正済み] ローカルツール環境にビルド・検査依存が不足

- 対象：`.venv`、`scripts/requirements-font-tools{,.lock}.txt`、`scripts/check-font-tools.py`、`docs/FONT-TOOLS.md`、`docs/BUILDING.md`。
- 症状：独立測定はSciPy不足で停止。MonoはTTF・ヒント付け後にBrotli不足でWOFF2生成が停止。
- 修正：Brotli／SciPy／scikit-imageを導入し、依存リスト・ロック・導入確認・Windowsでの実行手順に反映。`pip check` は成功。
- 根拠：`work/codex-review/sans-scan.log`（修正後）、`mono-rebuild.log`（初回失敗）、`mono/rebuild-complete/build-log.json`、`mono/rebuild-verify.log`。修正後のMono再生成・WOFF2・既存検査はexit 0、失敗0。
- 再現：`.venv/Scripts/python.exe -I -X utf8 -m pip install -r scripts/requirements-font-tools.lock.txt`。実ビルドは末尾のコマンドを参照。
- 確かさ：確認済み。新しい空venvからの全パッケージ再導入までは行っていない。

### [P2・修正済み] 修復見本が95字のうち48字しか出力しない

- 対象：`scripts/sans30/proof_sans_30.py:light_repair`。
- 症状：既定の12列×4行でリストを切り捨てる。見本だけでは後半47字を確認できない。
- 修正：既定で全リストから必要な行数を求め、95字すべてを出力する。明示した行数の制限は維持。
- 根拠：修正後の `work/codex-review/proofs/light-repair-before-after.png`。独立した95字×Light/Regular/Mediumの見本は `repair-FridaySans-1〜5.png`、`repair-FridaySansUI-1〜5.png`。全10枚を目視した。
- 確かさ：確認済み。見本の不足を修正したもので、以前の目視作業全体が48字のみだったと断定するものではない。

### [P2・修正済み] 配布説明の検査結果・収録範囲・描画差が不正確

- Sans配布README：解消済みの「ゼロ幅結合記号がGDEF markでないFAIL」を削除。`palt`／`halt`未対応とJIS X 0213の26区点未収録を明記。
- Mono配布README：公開5.0からの8スタイルの輪郭一致と、ヒント変更による描画差を区別。WinAscent 1000→1164も明記。
- `docs/BUILDING.md`：Monoのパッケージ生成先の説明を候補5.0.3に対応させ、WindowsのPython・環境変数・隔離出力手順を補足。
- 根拠：`metadata/{audit,features,packages,jis0213}.json`、`mono/published-comparison.json`、`mono/published-raster.json`。
- 確かさ：確認済み。JIS X 0213の欠落は2.5からの回帰ではない。

### [P3] Monoの描画不変という主張は成立しないが、検査画像では明確な破綻なし

- 対象：Light以外の8スタイル、主に積みアクセント。公開5.0との9/10/11/12/13/14/16/20/24pxの全字形比較で画像差あり。
- 切り分け：Regular／Boldでは `head.flags` のみ、またはOS/2 ascentのみの変更で画像差0。候補の字形TT命令と `cvt` を旧版に移すと、候補と全字形・全検査サイズで完全一致。原因は再ヒント付け。
- 13pxのRegular15字・Bold29字を旧／新で目視し、顕著な断線・白抜きの破綻を確認していない。他サイズ・実アプリの全差分の外観承認は未実施。
- 再現・画像：`mono/raster-isolation{,-hints}.json`、`mono/published-diff-{Regular,Bold}.png`。描画不変の表現は配布文書で訂正した。
- 確かさ：原因の切り分けは確認済み。全環境で無害という結論ではない。

### [P3] Mono +6/+7 の失敗は現行ヒント補正の制約

- +6を隔離再生成してLight 8サイズ・LightItalic 4サイズの数字不揃いを再現。+7も独立描画でLight 7サイズ・LightItalic 6サイズを再現。
- +5/+6/+7の数字の輪郭yMin/yMaxは同じ。+6 Lightでは7と9が同時にずれ、`rehint.one_digit_control` は全失敗サイズで外れる数字が1字の場合だけ補正するため、補正されない。Italicでは9の下端差が残る。
- `mono/hint-investigation.json`、`hint-grow-comparison.png`。現在の+5候補は検査を通る。+5が書体の絶対的な太らせ上限・最適値という証明ではないため、現候補の量を変更する根拠にはしない。
- 確かさ：失敗と補正処理の制約は確認済み。ttfautohint内部の認識が変わる詳細機序は未特定。

### [P3・既知事項の再評価] Sans Boldのℏ／∊の幅と外観の最終判断

- SansのLight〜SemiBoldでは両文字の送りが1000、Boldはℏ1226／∊1202（upem2000）。Sans UIでは全ウェイト1980。独立測定と `math-weights-1.png` で再確認した。
- 輪郭の欠画・異常な基線ずれはこの見本では確認していない。比例幅の書体でウェイト間の送りを完全一致させることは必須条件ではなく、縮幅・移動による外観変更を正当化する新しい根拠までは得られていないため、字幅を自動変更していない。
- 数式中でBoldだけ余白が増える性質は残る。半角固定を製品仕様にする場合は、輪郭位置・サイドベアリングを合わせて修正し、数式組版を再承認する必要がある。読み込み・画の欠けを理由とするP0判定にはしない。
- 確かさ：送りの差は確認済み。これを誤った字形設計と断定してはいない。

## Claude の主張の独立検証

| 項目 | 結果 | 根拠・限界 |
|---|---|---|
| A1 | 再現（確認範囲） | 両Lightの95字をRegular/Mediumと全数目視。旧楔・欠画は確認せず。Notoとの全共通漢字比較と、95字の厳しい比較も実施。修復方法固有の払い・鉤の形の差は残り、外観承認は別。 |
| A2 | 再現（測定・画像） | 全数の既存段差検査と独立面積測定。鬱・龍・議・響は対象Light/Regular/Mediumで3.001相当と同じ。Sans Mediumの齟0.9285倍・辯0.9382倍、2.5との比は1.019／1.0355倍。50%は工学的なガードであり最適なウェイト間隔を保証しない。 |
| A3 | 再現（確認範囲） | 記録された全融合候補をglyph IDで旧／新描画し全画像を目視。大きな欠画・新しい小片は確認せず。微小な隙間の全サイズ保証ではない。 |
| A4 | 再現 | 左上／右下の点を5ウェイトで目視。cmap/hmtx/vmtx・縦組み送り・UI幅・全/軽量WOFF2描画を独立検証。≒は既存＝の縦原点・幅を継承。字形のユーザー承認と縦組み実アプリは未確認。 |
| A5 | 再現 | ℊのBold下端−488とSemiBold−487（upem2000）は整合。`math-weights-1.png`。ℏ/∊のBold字幅は既知の不整合が残るが、フォント読込不能や画の欠けとは異なる。今回の新規破損としては扱わない。 |
| A6 | 再現 | Mn/Me/combをa/b間に入れる全数組版と代表ベトナム語・ウムラウト・合成濁音等。差は送り幅修正の対象のみ。既存dotbelowのhmtx/GDEF不整合はあるが、HarfBuzzは元からゼロ送りで今回の回帰ではない。 |
| A7 | 再現（テーブル）／実アプリは検証せず | 全20本にWindows name 1/2/4/6/16/17を保持、Mac/ltagなし、PS名一意。古いWord/Adobe/CoreTextの名前解決は未検証。 |
| A8 | 再現（輪郭・現候補） | 公開5.0 ZIPと8本の全字形座標・hmtx・cmap・順が一致。OS/2差もあるため「差はhint/name/head/paramsだけ」は訂正。Light31／LightItalic37の自己交差字形をglyph IDで全68字目視、顕著な破綻を確認せず。 |
| A9 | 再現せず（描画不変）／機能名は再現 | 上記の公開版との描画差を検出。ss01/cv01は全10本でzero→zero.altとなり名前と一致。整数ppemでのheadビット単独の影響は切り分けたが、全実エンジンの保証ではない。 |
| A10 | 再現（改良した検査） | 90 face×engineのロード・実画素差と文字別差を確認。旧状態検査だけの合格は採用していない。独立OTS単体は未実施。組版回帰・結合記号は別検査。 |
| A11 | 再現（設計・代表動作） | vert/vrt2各345置換が全10本で同一、代表縦組みで実置換あり。異なる2familyを一括比較したname/metric FAILは個別検査で解消。underline厚みのウェイト差は残る。 |

`vert`／`vrt2`を同時に適用しないという仕様上の扱いは [Microsoft OpenType specification](https://learn.microsoft.com/en-us/typography/opentype/spec/features_uz) を参照。併存だけを理由に出荷不可とする根拠は今回の実データでは得ていない。

## 全体監査の証拠

- Sans/UI 全10×16,759字形：FreeType glyph ID直接指定で9/10/11/12/13/14/16/20/24pxを描画。cmapにない異体字も含む。結果は `sans-allglyph-render.json`。
- 隣接ウェイトの全字形を、既存検査とは別のFreeType無ヒント192px/emで比較（幅中央をそろえ、4px許容・3px²の連結領域）。8ペアで96候補、空描画0。候補を `candidates-*.png` に全数出力して目視し、記号の字幅・結合記号の位置・線幅差以外の明確な破損を確認していない。ゼロ幅記号の見本は形を確認できるよう横縦に中央配置しており、組版位置はHarfBuzz検査で別に確認した。
- Noto Light／Regularとの独立比較：Sans/UIの各10,394共通字（BMP9,734＋拡張・互換等660）、計41,576 glyph ID画像比較で、160px/em・5px許容・8px²連結領域を超える候補0。修復95字は2px許容・2px²に絞り全数比較、両ファミリーの欠落領域最大5px²、8px²以上0。余剰インク候補67／55の上位40×2を参照と目視し、黒い楔・大きな欠画を確認していない。厳しい比較の残り55字まで参照と目視したという意味ではない。
- Inter opsz14・同wghtとのLatin／Greek／Cyrillic比較：全10本×各1,377共通letter、上位40×10を目視し明確な破損を確認していない。元入力と参照の版が完全に同じとは証明できず、cap高さ正規化により参照の線幅も変わるため多数の候補が出る。参照との差をそのまま不具合や全数合格と扱わない。詳細は `metadata/additional-findings.md`。
- Mono 全10×1,251字形：FreeType glyph ID直接指定で9〜14pxの各整数サイズ、例外・空インク0。既存検査の9〜24px・数字・罫線・組版・WOFF2も成功。
- Sans/UI 全10×16,759字形：FontForge構造検査。自己交差71,286件、extrema不足33,709件（書体×字形の件数）。open path・方向等のその他ビット0。自己交差の大量検出を正常性の証明や全数の破損判定には使わない。重なる輪郭を含むため、描画・ウェイト・元書体比較も併用した。
- 標準検査の既知輪郭数変更リストも、融合候補とは別に全10書体で旧／新を目視した（`known-contours-*.png`）。修復前の魃の異常を確認し、新版の見本ではその異常や明確な新しい画の破損を確認していない。
- 全20本のWin値は全非空字形の外接を覆う。Sans2660/1083、UI2634/1072、upem2000。fsType0、ベンダーFRDY、PS名20本一意。行高1.8715em／1.853emは設計判断として記録し変更しない。
- JIS X 0208の全区点を独立codec列挙しSans/UIの欠落0。JIS X 0213:2004は11,233レコード、25複数codepoint対応、26区点未収録。2.5から収録喪失0。IVS format14は存在するが登録簿の全数照合ではない。
- README数値を独立確認：TTF10本、全字形WOFF2 10本、軽量WOFF2 10本、Sans16,759字形／15,234収録文字、Mono1,251字形／1,062収録文字、upem2000、Sans行高約1.87em、em/en space幅1000/2000。5項目以上を実測した。
- 元候補ZIPの全ハッシュ・manifest・作業出力との一致を確認。修正後の出荷候補は `work/codex-review/shipping/` に別保存し、フォントバイトを保持したまま文書・画像・検証結果を更新する。元のZIPや既存 `work/` 出力は上書きしない。
- Sans再生成TTF全10本：全座標・端点・flags・hmtx・cmap・字形順・nameが元候補と一致。全テーブル差はheadの日時／checksumのみ。Mono再生成TTF／WOFF2もhead以外のdecoded tableが一致。
- Sans再生成WOFF2全20本：Brotli展開後、glyf等の変換テーブルを含む全ストリーム・変換設定・元長が一致（headの日時／checksumを除く）。これは輪郭の意味の一致より強い比較。`sans-web-stream-comparison.json`。全テーブルを再構成してコンパイルし直す比較は非常に重かったため、最初の2本の一致確認後に中止し、全20本をこの方法で完了した。

## 未検証・残る条件

1. **ClearType 実機は未確認**。GDIのGRAY8全字形検査やPlaywrightの画像は、実画面・Office/WPF/WinUIの目視確認の代替ではない。ClearTypeを有効にするOS設定の変更は行っていない。
2. macOS/iOS/Android、古いMac/Adobe/Windowsアプリの実動作。現在の環境に該当端末・アプリがない。
3. 全字形・全サイズ・全機能・全言語の人による目視。機械検査は全字形でも外観の全数承認ではない。
4. 人名用／常用漢字の公式表・IVS登録簿の全数照合、独立OTS単体。JIS codecとcmapの検査だけでこの範囲を済ませたとは扱わない。
5. ss02〜ss08／cv02〜cv14の全意味・全組合せの網羅。存在・名前参照・代表機能の実動作と回帰は確認した。
6. 3.001の実物はローカルにない。比較は再現3.001相当であり、公開原物とのバイト照合ではない。
7. Light/SemiBold、≒、手描きかなの好み・完成度のユーザー承認。機械検査から「最高品質として承認済み」とは記載しない。

## 再現手順と出力

すべてリポジトリルートで実行。既存の `work/` を上書きしない新規出力先を使う。環境変数はそのプロセスでのみ設定した。

```powershell
./.venv/Scripts/python.exe -I -X utf8 scripts/sans30/build_sans_30.py --src work/sans-3.0/x/FridaySans-2.5/ttf --out work/codex-review/sans-rebuild/ttf
./.venv/Scripts/python.exe -I -X utf8 scripts/sans30/verify_sans_30.py --src work/sans-3.0/x/FridaySans-2.5/ttf --out work/codex-review/sans-rebuild/ttf --report work/codex-review/sans-verify.json
./.venv/Scripts/python.exe -I -X utf8 scripts/sans30/make_web.py --ttf work/codex-review/sans-rebuild/ttf --out work/codex-review/sans-rebuild/web
$env:MONO_LIGHT_GROW='5'
$env:MONO_OUT='work/codex-review/mono/rebuild-complete'
./.venv/Scripts/python.exe -I -X utf8 scripts/mono50/build_mono_50.py
./.venv/Scripts/python.exe -I -X utf8 scripts/mono50/verify_mono_50.py
```

独立スクリプト：`sans_scan.py`（全字形・ウェイト間のFreeType画像比較）、`sans_allglyph.py`、`sans_proofs.py`（再生成比較）、`target_proofs.py`、`candidate_proofs.py`、`sans_gdi_prepare.py`／`sans_gdi.ps1`、`metadata/*.py`、`mono/*.py`。場所はすべて `work/codex-review/`。ブラウザ・FontForge・Fontspectorの正確な実行コマンドと負例は `browser/notes.md` に保存。入力フォントとツールの場所は `docs/FONT-TOOLS.md` を参照。

出荷候補の作成・全ZIPエントリの照合は `.venv/Scripts/python.exe -I -X utf8 work/codex-review/repackage.py`。結果は `shipping/verification.json` とZIP横の `.sha256`。再生成TTFは比較専用で、出荷候補には元候補のTTF/WOFF2バイトを使用する。

途中のログにある `name id ... missing` は2.5入力の失われたFeatureParams名についての警告であり、出力の名前参照検査と区別する。

## 最終集計

- Sans標準検査は全10本の字形／テーブル検査、8ウェイト対、8段差対が問題0で、終端は `OK: no problems`。出力JSONも生成された。ただしPowerShell 5系の `2>&1` が入力の警告を `NativeCommandError` にしたため、ツールが返したシェル終了コードは1だった。コマンドのexit 0とは記載しない。検査本体の集計とシェルのstderr扱いを区別する。再実行時はログ採取後に `exit $LASTEXITCODE` を指定するか、Pythonのsubprocessでstdout/stderrをファイルへ渡す。
- Sans/UIのGDI全字形13サイズ：2,178,670件、エラー0。FreeType全glyph IDの9サイズ：空・例外・縦つぶれ0。
- 全20 TTF再生成の輪郭・メトリクス・名前照合、Sans WOFF2全20本の展開ストリーム照合、Mono WOFF2全10本のテーブル照合を完了。
- ブラウザ90 face×engineが成功。組版はSans4,400件完全一致、Mono4,400件はLight系縦yオフセットのみ2units許容で一致。改良した検査の異常系は8＋7試験が成功。
- `work/codex-review/final-checks.json` に機械集計と検査対象20 TTFのSHA-256を固定する。出荷候補ZIPの全エントリ／manifest／SHA256SUMS照合は `shipping/verification.json` に保存する。
