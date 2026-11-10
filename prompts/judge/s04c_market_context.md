# 週次（判定）｜4c. 市場全体とテック内部
# prompts/judge.md の「ひな形」の表から、この節を書く直前に読む。

- 見出し：`### 4c. 市場全体とテック内部`
- （market-data の signals.json から転記、再計算しない。表1つ＋3行）：
  表の行＝テック内部（`breadth_ext.groups.tech`：pct_down20、4週前、pct_above_50sma、ラベル、XLK の bench_pct_from_52w_high）、
  それ以外（`groups.ex_tech`：pct_down20、4週前、pct_above_50sma）、S&P500全体（`groups.sp500`：pct_down20、ラベル、SPY の位置）、
  ブレイクの伸び（`breakout_followthrough_market`：d5_hold_rate、d5_avg_ret_pct、d10_avg_ret_pct、stalling、stalling_4w_ago）、
  市場Tape（`tape.regime_effective`、`tape.reasons`、`tape.checklist.IX3_index_breakdown_guard`、IX2、`megacap_led`）。
  ラベルは `breadth_ext.label_ja` の日本語で書く。
  1行目：今週の変化（key_events ではなく、前回YAMLの MARKET_CONTEXT との比較）。
  2行目：S2・S4との整合（例：「S4はSOXXの対SPYで−2、テック内部も broad_decline で整合」）。
  megacap_led が真なら「市場全体の中身の改善を半導体の追い風と読まない」と書く。
  表に次の行を足す：先導セクター（`leadership.market.top_sectors_now` と `leadership.by_sector` の上位3の数、4週前）、半導体・テクノロジーの先導株数（`leadership.tech`：今／4週前、半分以下か。`by_group` の半導体の数と銘柄）、
  半導体の新規・脱落（`new_leaders_vs_4w`／`dropped_leaders_vs_4w` のうち in_universe が真で、かつ semis-data の config.json `breadth_sets.semis_broad` に含まれる銘柄。要素に半導体の印は無いのでこの集合で判定する）、ヘッジ条件（`hedge.allowed`・`status`・`setups` の銘柄と損切り）、長期SPY配分モデル（`spy_model.allocation_pct`・`signal`・`signal_since`）。
  3行目：半導体が市場に引っ張られているか置いていかれているかを1行（先導株数の推移から）。
  ヘッジと長期の目安は米国株側の条件の転記であり、本レポートの売買指示ではない
