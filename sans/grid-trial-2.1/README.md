# Friday Sans Grid Trial 2.101

Friday Sans 2.1の結合濁点・半濁点の配置修正と「𠮷」を含む比較用試作。ファミリー名は **Friday Sans Grid Trial**。通常のFriday Sansと区別して選択できる。

既存の漢字のヒントだけを11〜18 device ppemに限定して戻す。仮名・英数字は2.1と同じ。範囲外では全グリフの描画が2.1と一致することをFreeTypeで検査した。新しく追加した「𠮷」にはヒントを付けていない。

FreeTypeでは特にRegularの漢字の線がまとまる結果が得られた。**Windows実機での品質は未確認。** サイズ・画面倍率・アプリを合わせて通常2.1と比較する。

デスクトップ用は`ttf/`、Web用は`web/`。比較HTMLは`../dist-2.1/windows-check.html`に内蔵済み。検査は`validation.json`、詳細は通常2.1のREADME.mdを参照。

字体・収録文字・行メトリクスは通常2.1と同じ。日本語palt / halt、くの字点の旧GDIクリップ、収録文字以外のフォールバックの制限も同じ。

利用・再配布条件は同梱`OFL.txt`と`licenses/`を参照。
