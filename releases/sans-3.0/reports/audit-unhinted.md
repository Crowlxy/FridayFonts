# Friday Sans 3.002: ヒントなしの影響の監査（生出力）

実行: `FridayFonts/work/sans-3.0` で `python ../../scripts/sans30/audit_unhinted.py --out audit/audit-unhinted.json --kanji 600` と下の3本。参照フォントは `reference/` の Hiragino W3・Noto Sans JP（wght 400）・Inter（opsz 14・wght 400 に固定）・SF Pro Text Regular。各字を1字ずつ測り、平均にしていません。

## 1. 高さ（audit_height_audit.py）
```
値は em の千分率(‰)。12px 換算は ×0.012 px/‰ → 1‰=0.012px(12px)、0.016px(16px)
                                                           Friday Sans 3.0 Friday Sans 2.5 Hiragino W3     Noto Sans JP    Inter           SF Pro Text    
x-height flat tops (u v w x y z)                           range  0.0‰ sd 0.0 range  0.0‰ sd 0.0 range  7.0‰ sd 2.6 range  0.0‰ sd 0.0 range  0.0‰ sd 0.0 range  0.0‰ sd 0.0
x-height round tops (c e o s)                              range  1.0‰ sd 0.4 range  1.0‰ sd 0.4 range  1.0‰ sd 0.4 range  0.0‰ sd 0.0 range  0.0‰ sd 0.0 range  0.0‰ sd 0.0
x-height all (a c e m n o r s u v w x z)                   range 12.0‰ sd 5.3 range 12.0‰ sd 5.3 range 16.0‰ sd 5.9 range 14.0‰ sd 6.8 range  9.8‰ sd 3.6 range  9.3‰ sd 4.5
cap flat tops (E F H I K L M N T V W X Y Z)                range  0.0‰ sd 0.0 range  0.0‰ sd 0.0 range  7.0‰ sd 3.2 range  0.0‰ sd 0.0 range  0.0‰ sd 0.0 range  0.0‰ sd 0.0
cap round tops (C G O Q S)                                 range  1.0‰ sd 0.4 range  1.0‰ sd 0.4 range  3.0‰ sd 1.0 range  0.0‰ sd 0.0 range  0.0‰ sd 0.0 range  0.0‰ sd 0.0
cap all (A-Z)                                              range 12.0‰ sd 4.4 range 12.0‰ sd 4.4 range 16.0‰ sd 5.6 range 13.0‰ sd 5.1 range  9.8‰ sd 3.8 range 16.6‰ sd 6.5
digit tops (0-9)                                           range 12.0‰ sd 5.6 range 12.0‰ sd 5.6 range 16.0‰ sd 5.3 range 13.0‰ sd 6.2 range  9.8‰ sd 4.8 range 16.6‰ sd 7.5
baseline flat bottoms (E F H I K L M N Z b d h i k l m n r range 10.0‰ sd 3.4 range 10.0‰ sd 3.4 range 10.0‰ sd 3.9 range 13.0‰ sd 4.9 range 11.7‰ sd 3.5 range  9.3‰ sd 3.1
baseline round bottoms (C G O S c e o s 0 6 8 3)           range  1.0‰ sd 0.4 range  1.0‰ sd 0.4 range  5.0‰ sd 1.5 range  0.0‰ sd 0.0 range  2.9‰ sd 1.1 range  7.3‰ sd 3.4
baseline all A-Za-z0-9 excl. descenders                    range 12.0‰ sd 5.2 range 12.0‰ sd 5.2 range 16.0‰ sd 6.1 range 13.0‰ sd 6.3 range 12.7‰ sd 5.1 range 16.6‰ sd 6.5
x-height overshoot o - x (‰) / O - H (‰)                   12 / 11         12 / 11         13 / 15         14 / 13         7 / 10          9 / 17         
x/cap/digit1/zero top (‰)                                  546/768/768/778 544/765/765/776 545/766/771/780 543/733/733/746 546/728/728/737 526/705/705/721
```

## 2. 字ごとのインク面積の比（audit_ink_ratio.py）
```
== Friday 3.0 / Friday 2.5  (ink area, same character)
  lower     n= 26 median ratio 1.072 | per-glyph p5 1.070 p95 1.077 | glyphs off the class median by >10%:   0 (0.0%), >20%: 0, worst 1%
  upper     n= 26 median ratio 1.067 | per-glyph p5 1.065 p95 1.070 | glyphs off the class median by >10%:   0 (0.0%), >20%: 0, worst 0%
  digit     n= 10 median ratio 1.070 | per-glyph p5 1.067 p95 1.072 | glyphs off the class median by >10%:   0 (0.0%), >20%: 0, worst 0%
  hiragana  n= 83 median ratio 1.079 | per-glyph p5 1.072 p95 1.084 | glyphs off the class median by >10%:   0 (0.0%), >20%: 0, worst 1%
  katakana  n= 86 median ratio 1.077 | per-glyph p5 1.072 p95 1.084 | glyphs off the class median by >10%:   0 (0.0%), >20%: 0, worst 1%
  kanji     n=600 median ratio 1.083 | per-glyph p5 1.021 p95 1.094 | glyphs off the class median by >10%:   0 (0.0%), >20%: 0, worst 6%
== Friday 3.0 / Hiragino W3
  lower     n= 26 median ratio 1.013 | per-glyph p5 0.918 p95 1.071 | glyphs off the class median by >10%:   1 (3.8%), >20%: 0, worst 10%
  upper     n= 26 median ratio 1.037 | per-glyph p5 1.005 p95 1.090 | glyphs off the class median by >10%:   1 (3.8%), >20%: 0, worst 13%
  digit     n= 10 median ratio 1.032 | per-glyph p5 0.972 p95 1.087 | glyphs off the class median by >10%:   0 (0.0%), >20%: 0, worst 6%
  hiragana  n= 83 median ratio 1.070 | per-glyph p5 0.965 p95 1.178 | glyphs off the class median by >10%:  10 (12.0%), >20%: 0, worst 16%
  katakana  n= 86 median ratio 1.070 | per-glyph p5 1.001 p95 1.180 | glyphs off the class median by >10%:   6 (7.0%), >20%: 0, worst 15%
  kanji     n=600 median ratio 1.071 | per-glyph p5 1.006 p95 1.125 | glyphs off the class median by >10%:   2 (0.3%), >20%: 0, worst 11%
== Friday 3.0 / Noto Sans JP 400
  lower     n= 26 median ratio 0.909 | per-glyph p5 0.823 p95 1.078 | glyphs off the class median by >10%:   6 (23.1%), >20%: 1, worst 22%
  upper     n= 26 median ratio 1.028 | per-glyph p5 0.954 p95 1.149 | glyphs off the class median by >10%:   3 (11.5%), >20%: 0, worst 17%
  digit     n= 10 median ratio 1.106 | per-glyph p5 0.894 p95 1.169 | glyphs off the class median by >10%:   1 (10.0%), >20%: 1, worst 30%
  hiragana  n= 83 median ratio 0.961 | per-glyph p5 0.933 p95 0.981 | glyphs off the class median by >10%:   0 (0.0%), >20%: 0, worst 9%
  katakana  n= 86 median ratio 0.938 | per-glyph p5 0.926 p95 0.948 | glyphs off the class median by >10%:   0 (0.0%), >20%: 0, worst 7%
  kanji     n=600 median ratio 0.928 | per-glyph p5 0.896 p95 0.950 | glyphs off the class median by >10%:   0 (0.0%), >20%: 0, worst 5%
== (参考) Friday 2.5 / Hiragino W3
  lower     n= 26 median ratio 0.946 | per-glyph p5 0.857 p95 0.999 | glyphs off the class median by >10%:   1 (3.8%), >20%: 0, worst 11%
  upper     n= 26 median ratio 0.972 | per-glyph p5 0.939 p95 1.022 | glyphs off the class median by >10%:   1 (3.8%), >20%: 0, worst 13%
  digit     n= 10 median ratio 0.967 | per-glyph p5 0.909 p95 1.016 | glyphs off the class median by >10%:   0 (0.0%), >20%: 0, worst 6%
  hiragana  n= 83 median ratio 0.994 | per-glyph p5 0.896 p95 1.085 | glyphs off the class median by >10%:   9 (10.8%), >20%: 0, worst 16%
  katakana  n= 86 median ratio 0.993 | per-glyph p5 0.925 p95 1.093 | glyphs off the class median by >10%:   5 (5.8%), >20%: 0, worst 15%
  kanji     n=600 median ratio 0.996 | per-glyph p5 0.949 p95 1.044 | glyphs off the class median by >10%:   2 (0.3%), >20%: 0, worst 12%
== Friday 3.0 / Inter
  lower     n= 26 median ratio 0.926 | per-glyph p5 0.875 p95 0.948 | glyphs off the class median by >10%:   0 (0.0%), >20%: 0, worst 7%
  upper     n= 26 median ratio 0.962 | per-glyph p5 0.948 p95 1.018 | glyphs off the class median by >10%:   0 (0.0%), >20%: 0, worst 7%
  digit     n= 10 median ratio 0.981 | per-glyph p5 0.943 p95 1.044 | glyphs off the class median by >10%:   0 (0.0%), >20%: 0, worst 8%
== Friday 3.0 / SF Pro Text
  lower     n= 26 median ratio 0.990 | per-glyph p5 0.946 p95 1.035 | glyphs off the class median by >10%:   0 (0.0%), >20%: 0, worst 7%
  upper     n= 26 median ratio 1.042 | per-glyph p5 1.006 p95 1.100 | glyphs off the class median by >10%:   0 (0.0%), >20%: 0, worst 6%
  digit     n= 10 median ratio 1.026 | per-glyph p5 0.993 p95 1.081 | glyphs off the class median by >10%:   0 (0.0%), >20%: 0, worst 6%
== (参考) Noto / Hiragino W3
  lower     n= 26 median ratio 1.108 | per-glyph p5 0.990 p95 1.207 | glyphs off the class median by >10%:   4 (15.4%), >20%: 0, worst 18%
  upper     n= 26 median ratio 1.018 | per-glyph p5 0.937 p95 1.108 | glyphs off the class median by >10%:   2 (7.7%), >20%: 0, worst 13%
  digit     n= 10 median ratio 0.910 | per-glyph p5 0.878 p95 1.220 | glyphs off the class median by >10%:   1 (10.0%), >20%: 1, worst 55%
  hiragana  n= 83 median ratio 1.118 | per-glyph p5 1.013 p95 1.213 | glyphs off the class median by >10%:   6 (7.2%), >20%: 0, worst 17%
  katakana  n= 86 median ratio 1.141 | per-glyph p5 1.065 p95 1.247 | glyphs off the class median by >10%:   4 (4.7%), >20%: 0, worst 15%
  kanji     n=600 median ratio 1.154 | per-glyph p5 1.096 p95 1.215 | glyphs off the class median by >10%:   3 (0.5%), >20%: 0, worst 12%
```

## 3. 位相ごとの濃さのゆれ（audit_phase_worst.py）
```
Friday Sans 3.0  12 worst: l:0.50 i:0.44 j:0.37 r:0.34 m:0.30 k:0.24 J:0.24 L:0.23 b:0.22 T:0.21 | mean range 0.119
Friday Sans 3.0  14 worst: L:0.24 I:0.21 1:0.18 B:0.17 D:0.16 H:0.16 E:0.16 J:0.15 P:0.13 u:0.12 | mean range 0.068
Friday Sans 2.5  12 worst: l:0.50 i:0.46 j:0.39 r:0.36 m:0.31 f:0.28 k:0.25 J:0.24 b:0.22 L:0.22 | mean range 0.123
Friday Sans 2.5  14 worst: H:0.27 L:0.24 I:0.21 U:0.19 B:0.18 D:0.18 1:0.18 E:0.17 N:0.16 J:0.15 | mean range 0.072
Hiragino W3      12 worst: I:0.46 L:0.46 l:0.27 i:0.26 1:0.26 F:0.23 E:0.21 J:0.20 K:0.17 R:0.17 | mean range 0.106
Hiragino W3      14 worst: l:0.21 i:0.16 J:0.16 m:0.15 j:0.14 d:0.14 T:0.14 f:0.14 q:0.13 r:0.13 | mean range 0.079
Noto Sans JP     12 worst: 1:0.25 l:0.18 m:0.17 u:0.17 T:0.17 i:0.17 j:0.16 r:0.16 f:0.15 2:0.14 | mean range 0.084
Noto Sans JP     14 worst: E:0.12 B:0.12 L:0.12 D:0.11 4:0.11 F:0.10 l:0.09 I:0.09 j:0.08 P:0.07 | mean range 0.042
Inter            12 worst: l:0.33 i:0.28 j:0.25 L:0.23 r:0.23 h:0.21 I:0.20 n:0.20 H:0.19 B:0.18 | mean range 0.097
Inter            14 worst: r:0.12 T:0.11 1:0.10 l:0.10 Z:0.09 n:0.09 h:0.09 q:0.08 0:0.08 d:0.08 | mean range 0.043
SF Pro Text      12 worst: l:0.34 i:0.28 F:0.28 u:0.25 T:0.24 j:0.24 n:0.24 1:0.23 L:0.22 r:0.21 | mean range 0.103
SF Pro Text      14 worst: I:0.21 L:0.19 1:0.14 r:0.12 u:0.11 g:0.11 T:0.10 f:0.09 J:0.09 2:0.09 | mean range 0.058
```
