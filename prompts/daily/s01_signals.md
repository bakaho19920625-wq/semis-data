# 1. 本日のシグナル

- 見出し：`### 1. 本日のシグナル（high○件、medium○件）`。low があれば「low○件」も書く。
- daily_signals.json の signals をすべて列挙する。空なら「検出なし」。
severity high → medium の順。
1行＝「銘柄：内容」。
コードが出したものを削らない。
解釈は次節で。
まとめ方（削らずに、並べ方だけ変える。見出しに件数「high○件、medium○件」を書く）：
- 1日の騰落（`big_move`）が同じ向きに6件以上ある日は、向きごとに1行にまとめる。
  例「1日で大きく上げた：23（SOX +6.9%、SOXX +7.5%、SMH +5.1%、SOXL +22.3%、DRAM +6.3%｜AMD +13.3%、TER +12.7%、ONTO +12.0%、…）」。
  指数・ETFを先に、個別は騰落率の大きい順に、全銘柄を括弧の中に並べる。
- 逆向きの銘柄（全面高の日に下げた銘柄、全面安の日に上げた銘柄）と、出来高を伴う上昇・下落（`volume`）は、1銘柄ずつ別の行に書く（例「NVDA：出来高が20日平均の3.88倍で下落（−4.27%）」）。
- `rsi`・`sma_cross`・`new_high_low`・`drawdown` は種類ごとに1行（銘柄と数字を並べる）。
- 状態の変化（`health_label_change`・`risk_count_change`・`washout_count_change`・`washout_phase_change`・`rs_strip_state_change`・`level_change`・`adr_premium`・`sector_rs_flip` など）は1件ずつ。
`health_label_change`・`risk_count_change`・`washout_count_change`・`rs_strip_state_change`、`washout_phase_change`（ticker は SEMIS／SOXX）もここに含める。
0節と重なってよい。
