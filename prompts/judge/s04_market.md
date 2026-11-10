# 週次（判定）｜4. 市場構図、4a. セクター内の強弱、4b. 調整耐性
# prompts/judge.md の「ひな形」の表から、この節を書く直前に読む。

- 見出し：`## 4. 市場構図`、その下に `### 4a. セクター内の強弱`、`### 4b. 調整耐性`（4c・4d は別のファイル）
- 4節の本文は、これまでどおり「事実」「解釈」「反証・懸念」「予測への含意」に分けて書く（judge.md 共通ルール）。既存の内容に加えて、その下に 4a〜4d を置く。

## 4a
- `resilience.json` の `sector_rs`（`semis_snapshot.csv` の `sector_rs_class`）から、リーダー上位5・ラガード下位5（rs_soxx_60順）。
  列＝銘柄、rs_soxx_20、rs_soxx_60、dd_vs_soxx_pt、RSライン60本高値。
  前回からの flip（leader⇄laggard）を1行

## 4b
- `resilience.json` の `window` を1行（state、high_date、low_date、dd_low、dd_now。「なし」「浅い調整」はその旨）。
  `next_candidates` をA→B→Cで最大8行（銘柄、下げ耐性区分、R_held、戻り区分、R_now、新高値）。
  `late_breaks`（後崩れ）を1行。
  MU・SNDK・SKHYがどこに位置するかを1文。
  値は転記し、再計算しない
