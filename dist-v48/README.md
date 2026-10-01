# Friday Mono v48

Friday Mono / Friday Mono Plain、各 Regular・Medium・Bold と Italic の計12本。
内部バージョンは Version 4.800。欧文600・和文1200、UPM 1000の日本語等幅フォントです。

## v47からの変更

書体名を **Inori Mono（旧名）→ Friday Mono** に変更しました（Plain も **Friday Mono Plain**）。
輪郭・字幅・ヒント・OpenType機能は v47 とバイト単位で同一で、書き換えたのは名前情報（name テーブル）と版番号だけです。
旧名の v47 を入れている場合は、先に削除してからインストールしてください（別名なので両方入ってしまいます）。

v47 で行った Windows（WPF）実機確認の結果は、字形データが同一のため v48 にもそのまま当てはまります。

## 配布物

- `ttf/`：Windows / macOS / Linuxのインストール用TTF。
- `web/`：ブラウザ用WOFF2と `friday-mono.css`。TTFフォールバック付き。
- `OFL.txt` / `licenses/`：ライセンス・原著作権表示。
- `font-manifest.json` / `SHA256SUMS.txt`：ファイル検証用。

Friday Mono は斜線入りゼロ、Plain は斜線なし。両方を同時に導入できます。
`ss01` / `cv01` はゼロを反転、Plainの `zero` は斜線入りに切り替えます。

## インストール

Windows：旧版の同名フォントを削除し、対象TTFを右クリックして「インストール」。
全ユーザー用のインストールには管理者権限が必要な場合があります。使用中のアプリを再起動してください。

macOS：旧版の重複をFont Bookで解消し、対象TTFを開いてインストール。
アプリを再起動し、必要ならOSを再起動してフォントキャッシュを更新してください。

Linux：対象TTFを `~/.local/share/fonts/` に配置して `fc-cache -f` を実行します。

古いWindowsアプリではMediumが「Friday Mono Medium」という別ファミリに表示されます。
これはRegular / Italic / Bold / Bold Italicのスタイルリンクを守るための仕様です。
新しいアプリではFriday MonoのMediumとして選択できます。

## Web

`ttf/` と `web/` の相対位置を保ってサーバーへ配置します。

```html
<meta charset="utf-8">
<link rel="stylesheet" href="web/friday-mono.css">
<style>
  pre, code {
    font-family: "Friday Mono", monospace;
    font-weight: 400;
    line-height: 1.6;
    font-synthesis: none;
  }
</style>
```

Regular=400、Medium=500、Bold=700。斜体は `font-style: italic` で指定します。
Plainを使う場合は `font-family: "Friday Mono Plain", monospace` に変更します。
WOFF2を `font/woff2`、TTFを `font/ttf` で配信し、別ドメインから使う場合は適切なCORS許可を設定してください。
CSPを使うサイトではフォント配信元を `font-src` に許可してください。
必要なファミリとウェイトだけ読み込み、12本すべてをpreloadする必要はありません。

## 対応範囲と表示上の注意

日本語と欧文のコーディング用途が中心です。全世界の文字・絵文字を収録するフォントではありません。
未収録文字はアプリのフォールバックフォントが必要です。元データのUTF-8 / Shift_JISの取り違えはフォントでは修復できません。
Webやソースファイルは正しい文字コードで保存・宣言してください。

結合文字はゼロ幅とし、ccmp・mark・mkmkで合成・配置します。
対応するNoto CJKの異体字シーケンスはcmap format 14に格納しています。
縦書きはvert / vrt2と縦メトリクスを搭載しています。アプリ側のOpenType対応が必要です。
独自に調整した仮名の標準形と、元Notoの異体字の造形は同一ではありません。

既存の行間設計を保持しています。アクセントを多重に重ねたり、極端に小さい固定行高を設定した場合は行間で接触することがあります。
Webでは明示的な `line-height: 1.6` を推奨します。East Asian Ambiguous文字の1桁/2桁扱いはターミナル設定により変わります。

## ライセンス

SIL Open Font License 1.1。商用の文書・画像・Webサイト・アプリで使用できます。
フォントを再配布する場合は著作権表示とOFLを維持してください。フォント単体の販売は禁止です。
改変版の一次フォント名にはReserved Font Name「Friday」を使わず改名してください。
原著作権者による推奨・公認を示すものではありません。正確な条件は同梱 `OFL.txt` を参照してください。

使用ソース：Iosevka Custom、Noto Sans CJK JP、および本プロジェクトの独自作図。
SF Mono / ヒラギノのフォントファイルは配布物に含みません。

公式資料：
- https://openfontlicense.org/ofl-faq/
- https://github.com/be5invis/Iosevka/blob/main/LICENSE.md
- https://github.com/notofonts/noto-cjk/blob/main/Sans/LICENSE

## 検証の位置づけ

同梱の品質調査報告を参照してください。実行できた環境と静的互換性検査を区別して記録しています。
未実施のOS・アプリまで実機検証済みとするものではありません。

外字：Windows-31Jのユーザー定義領域は共通の字形を定義していません。外字フォントが必要です。
`windows-smoke-test.ps1` はWindows上でTTFを直接読み込む確認用です。フォントをインストールしたりシステム設定を変えたりしません。
