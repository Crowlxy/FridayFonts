# Friday

日本語のための2つの書体。どちらも SIL Open Font License 1.1 で、商用でも無料で使えます。

| | 用途 | 欧文の元 | 和文の元 | 最新版 |
|---|---|---|---|---|
| **Friday Mono** | コーディング用の等幅（欧文 600 / 和文 1200） | Iosevka | Noto Sans CJK JP | v48（Version 4.800） |
| **Friday Sans** | 文章・UI 用のプロポーショナル | Inter | Noto Sans CJK JP | 1.1（Version 1.100） |

フォントは [Releases](../../releases) からダウンロードできます。
旧名は **Inori Mono**（v47 まで）。名前以外は v47 と同一です。

## Friday Mono

日本語と欧文を同じ濃度で組める等幅コーディング書体。Regular / Medium / Bold と各イタリック、
`0` に斜線の入った **Friday Mono** と斜線なしの **Friday Mono Plain** の計12本。

- SF Mono とヒラギノ角ゴを実測して設計原則を取り出し、OFL のフォント（Iosevka、Noto Sans CJK JP）の上で組み直しています
- 仮名の一部（と さ き ふ や と、そこから作った ど ざ ぎ ぶ ぷ ゃ）は本プロジェクトの手描き
- Windows でも仮名・漢字の高さが揃うよう、和文に専用のヒント（Chlorophytum）を入れています

使い方・インストール方法は [RELEASE-v48.md](RELEASE-v48.md)、設計の根拠は [DESIGN.md](DESIGN.md)。

## Friday Sans

Friday Mono と同じ和文（手描きの仮名を含む）に、Inter の欧文を組み合わせたプロポーショナル書体。
Regular / Medium / Bold の3本。macOS の標準（SF Pro + ヒラギノ角ゴ）と同じ大きさ・字間の考え方で組んであり、
太さは和欧混植の見本を見て、それより少し軽く決めています。

使い方・設計は [sans/RELEASE-1.1.md](sans/RELEASE-1.1.md)。

### SF Pro・ヒラギノのアウトラインは使っていません

Friday Sans は文章にすると macOS の標準表示とよく似て見えますが、**SF Pro とヒラギノ角ゴのアウトライン（字形データ）は1点も使っていません。**

- 欧文の字形は **Inter**、和文の字形は **Noto Sans CJK JP** と本プロジェクトの手描きの仮名だけから作っています。
- SF Pro Text とヒラギノ角ゴからは、大文字の高さ・縦画の太さ・平均字幅・行の高さといった**数値だけ**を測りました。測った値はすべてビルドスクリプト（`sans/build_sans.py`、`build_inori_v3.py`）の冒頭に定数として書いてあります。
- SF Pro とヒラギノのフォントファイルは、このリポジトリにも配布物にも含まれていません。

似て見えるのは、もともと SF Pro に近い系統の Inter を、大きさ・太さ・字間を揃えて使っているためです。
字形そのものは別物で、字を同じ高さに描いて重なる面積の割合（1.0 なら完全に同じ形）を比べると、元にしたフォントとの一致度は手本との一致度よりはっきり高くなります。

| Regular | 元にしたフォントと | 手本と |
|---|---|---|
| 欧文 13 字（a e g t y R G Q J 1 $ & @） | Inter と **0.97** | SF Pro Text と 0.86 |
| 和文 12 字（永 国 書 東 語 機 鬱 あ い う え お） | Noto Sans CJK JP と **0.95** | ヒラギノ角ゴ W3 と 0.69 |

重ねてみると、次のような違いがあります。

- **欧文**：Inter と SF Pro はもともと近い系統なので、違いは細部に出ます。`&` の上部と右下の脚、`J` の頭、`1` の旗、`a` `e` `t` の終筆の切り方と角度。Friday Sans の字形は Inter そのものです。
- **和文**：違いは大きく、`永` の払いの長さと角度、`機` の各部の位置、`鬱` の中の組み立て、`あ` `い` `う` `え` `お` の曲線の位置と張り方がずれます。Friday Sans の字形は Noto Sans CJK JP（と本プロジェクトの手描きの仮名）です。

数値は `sans/make_overlay.py` で再現できます（SF Pro とヒラギノが入った Mac が必要です）。
SF Pro・ヒラギノの字形を含む画像はライセンスに配慮してリポジトリに置かず、スクリプトがローカルにだけ書き出します。

## ライセンス

フォントは SIL Open Font License 1.1（[OFL.txt](OFL.txt)）。Reserved Font Name は「Friday」です。
改変して配布する場合は、この名前を使わずに改名してください。

元にしたフォントとその権利者：

| | ライセンス | 使用先 |
|---|---|---|
| Iosevka（Renzhi Li） | OFL 1.1 | Friday Mono の欧文 |
| Inter（The Inter Project Authors） | OFL 1.1 | Friday Sans の欧文 |
| Noto Sans CJK JP / Source Han Sans（Adobe、Reserved Font Name 'Source'） | OFL 1.1 | 両方の和文 |

## ビルド

`Source/`（このリポジトリの1つ上の階層）に Iosevka Custom、Noto Sans CJK JP の可変フォント、Inter 4.1 を置き、Python 3.12 の仮想環境で実行します。

```bash
./.venv/bin/python build_inori_v3.py --out fonts-v48 --approved-visual-review   # Friday Mono
./.venv/bin/python sans/build_sans_cjk.py && ./.venv/bin/python sans/build_sans.py  # Friday Sans
./.venv/bin/python sans/hint_sans.py                                               # Friday Sans のヒント
```

設計の詳細は [DESIGN.md](DESIGN.md)。
