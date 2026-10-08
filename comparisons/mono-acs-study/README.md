# ACS 5250向け：4.91の行高を保つ比較用フォント

比較用のファミリ名は `Mono ACS Study`、`Mono ACS Study JP`、`Mono ACS Study Plain JP`。5ウェイトと各Italic、計30本を `ttf/` に出力しています。Regular/Medium/Boldと各Italicはハッシュ一致の4.91を入力にし、Light/SemiBoldと各Italicは正規4.93 ZIPのハッシュ一致TTFを入力にしています。

この候補はC/Oを縮めていません。輪郭・字幅・ヒント・文字収録・GSUB/GPOS・ゼロ切り替えの全テーブルは元入力とバイナリ一致しています。既存18本は名前・版情報だけ、新ウェイト12本はさらに`hhea.descent`と`OS/2.sTypoDescender`を−400から−120に戻しています。全30本のascentは880、lineGapは0、UPMは1000、行高は1.000emです。下線位置−120、太さ60、Win ascent/descentは元のままです。変更前後とSHA-256は`validation.json`にあります。

## スクリーンショットで確認したこと

利用者指定の120039.png（4.93 SemiBold）と120053.png（4.91）の青色画素を測ると、先頭3行は次のようになっています。異なるウェイトと切り取り範囲なので、版の変更だけを原因と断定する比較ではありません。

| 項目 | 4.91画像 | 4.93 SemiBold画像 |
|---|---:|---:|
| 見えている文字の高さ | 15px | 13px |
| 文字下端から横下線までの空白 | 1px | 5px |
| 横下線どうしの間隔 | 21px | 21px |

画像のハッシュ、画素位置と測定方法は`screenshot-measurements.json`、再計測コードは`scripts/audit_acs_screenshots.py`です。固定の行枠の中で、文字が低くなり、下側の余白が増えた見え方を確認できます。

## ACSで使用中のJavaによる確認

実行中の`acslaunch_win-64.exe`のJVMは `C:/IBMiAccess_v1r1/Start_Programs/Windows_x86-64/jdk-11.0.8.10-openj9` です。`acsbundle.jar`のマニフェストはACS 1.1.9、driver 2171でした。同じJava 11.0.8を使い、フォントをインストールせず`Font.createFont`で個別に読み込んでAWTの行メトリクスを測定しました。

| 20px指定時のAWT値 | ascent | descent | 行高 | `SUS430-2D`の送り |
|---|---:|---:|---:|---:|
| 元4.91 Regular | 17.6 | 2.4 | 20.0 | 約108px |
| 元4.93 Regular / SemiBold | 17.6 | 8.0 | 25.6 | 約108px |
| 新しいACS候補（全30本） | 17.6 | 2.4 | 20.0 | 約108px |

つまり4.93では、同じ指定サイズと横送りでも、Javaが報告する縦の枠だけが広くなります。[IBMの公式説明](https://www.ibm.com/support/pages/why-are-ibm-i-acs-5250-characters-mis-aligned-when-font-scaling-enabled)では、Font Scaling有効時はセッションの枠に合わせて文字を縦横に拡縮します。この機能と4.93の行メトリクスの組合せが、縦の圧縮と下余白の増加を起こした可能性が高いと判断しています。利用者のFont Scaling設定自体は読み出していないため、確定診断ではありません。

記録は`java-metrics.txt`、Javaコードは`scripts/AuditMonoJava.java`。行高の下限だけ詰める1.198em案も、同じJavaでは23.96pxを報告するため、1.000emの4.91と同じ表示になるとは限りません。hheaを1.000emのまま、OS/2 typoだけ1.198emにする試験でもAWTの行高は23.96pxになり、ASとTerminalをその2テーブルだけで分ける案は成立しませんでした。

## 再生成と確認

リポジトリ直下で `py scripts/build_mono_acs_comparison.py`。Python/fontTools/Pillowと4.91のハッシュ一致入力、正規`FridayMono-4.93.zip`を使用します。`proof.png`は同一サイズでの全10スタイルの輪郭見本で、ACSのスクリーンショットではありません。

実機確認では、同じセッションサイズ・同じウェイト・同じItalic設定で、4.91とこの候補を比較してください。例：4.93 SemiBoldと比較するなら、候補のSemiBold（斜体ならSemiBold Italic）を選びます。まず文字高と下の空白、次に日本語・g/p/q/y・横下線・カーソルの収まりを確認します。

ACSは[追加フォントの公式機能](https://public.dhe.ibm.com/as400/products/clientaccess/solutions/GettingStarted_en.html#9.10)でフォントフォルダ／TTFを読み込めます。ただし既存ACS設定、追加フォント登録、インストールは変更していません。新候補を実際の5250セッションで表示した結果は未確認です。今回の実行済み確認は同じJavaでの個別フォント読込み・AWTメトリクスとバイナリ照合です。

この1.000em候補はWindows Terminalの8〜24pt全条件での二重線分離を保証しません。Terminal用の最小間隔候補は別の`../mono-tight-study/`です。Light/SemiBoldの欧文は4.93と同じ既存輪郭からの派生で、Iosevka本来のLight/SemiBoldではありません。正式リリース、インストール、コミット、公開は行っていません。ライセンスは`OFL.txt`。
