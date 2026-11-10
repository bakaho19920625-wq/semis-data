# 6b. 市場全体とテック内部

- 見出し：`### 6b. 市場全体とテック内部`
- market-data の signals.json（/home/claude/mkt_signals.json）から転記する。再計算しない。
- 分量：6行以内。
- 短縮形（「前日から変わった点」に、この節に関わる変化が無い日）：3行（市場全体とテック内部／先導セクター・ヘッジ・長く持つ分の目安／買い戻しの燃料と不安の指数の期間構造）。
- 基準日と版：signals.json の `as_of_market_date` が `us_as_of` と同じか確かめる（流れの側で待っても違うことがある）。
  違えば「基準日が異なる（market-data ○○）」と書いて、そのまま転記する。
  取得できなければ6b節は「取得できず」の1行。
  `definition_version` が `ST-1.4` より前なら、テック内部とブレイクの伸びは「未対応（旧版）」。
  `engine 1.3` より前なら先導セクター・ヘッジ・長期モデルは「未対応（旧版）」。
- 変化：`key_events_today` のうち type が `regime_change`・`breadth_label_change`・`index_breakdown_guard`・`breakout_stalling` のものを先頭に1行ずつ（なければ「変化なし」）。
- テック内部：`breadth_ext.groups.tech` の pct_down20（4週前 pct_down20_4w_ago）、pct_above_50sma、ラベル（`breadth_ext.label_ja[label]`、null は「ラベルなし」）、XLK の bench_pct_from_52w_high、ex_tech との差（`tech_minus_ex_tech_down20_pt`）。
  stealth なら「XLKは高値圏だが、IT＋通信の過半が高値から20%以上下げている（隠れ弱気）」、broad_decline なら「XLKも−10%超で下げが表面化」と添える。
- ブレイクの伸び：`breakout_followthrough_market` の d5_hold_rate、d5_avg_ret_pct、d10_avg_ret_pct、stalling。
  stalling が真なら「市場全体で、抜けた水準は守るが伸びないブレイクが多い。半導体の高値・水準の上抜けも、抜けた後の続き（D+3〜5）と出来高で確かめる」と添える。
- 市場全体：`tape.regime_effective` と `tape.reasons`、`tape.checklist.IX3_index_breakdown_guard`、`tape.checklist.megacap_led`。
  megacap_led が真なら「市場全体の中身は改善しているが、大型・AI株主導で指数が崩れている。市場全体の改善を半導体の追い風と読まない」と添える。
- 先導セクター：`leadership.market.top_sectors_now`（上位3と `leadership.by_sector` の数、4週前）、`leadership.tech`（半導体・テクノロジーの先導株数 今／4週前。`halved_vs_4w` が真なら「4週前の半分以下」）、`leadership.tech.by_group` の半導体の数と銘柄。
  `key_events_today` に leadership_shift があれば先頭の「変化」に入れる。
  「指数より先に先導株の分布が変わる。半導体が引っ張られているか置いていかれているかを見る」と1行。
- ヘッジと長期の目安：`hedge.allowed`・`hedge.status`・`hedge.setups`（銘柄、水準、損切り）を1行（許可外なら「検討できる地合いではない」）。
  `spy_model.allocation_pct`・`signal`・`signal_since` を1行「長く持つ分の目安 ○%（buy／sell、○月○日から）」。
  どちらも米国株側の条件の転記で、半導体の売買指示ではない。
- 買い戻しの燃料：market-data の main ブランチ `reports/flows/fuel_latest.yaml` を読む
  （`curl -sSf https://raw.githubusercontent.com/bakaho19920625-wq/market-data/main/reports/flows/fuel_latest.yaml -o /home/claude/mkt_fuel.yaml`。届かなければ「買い戻しの燃料：未取得」）。
  `fuel.bar` と `line_ja` を1〜2行でそのまま転記する（例「■■■■■■■■□□ 買い戻しの燃料：残り約8割（多い。11/6 週のデータ）。プロの買い持ちは過去5年でいちばん軽い…」）。
  `sector_note`（テック・半導体の持ち高についての発表元の言葉）があれば続けて1句。
  `updated_jst` が21日より古ければ「（古いデータ）」を付ける。
  水準の読み方（多い＝売る物が少なく買い戻しで上がりやすい位置だが上がる保証ではない／半分ほど＝買い戻しの途中／少ない＝買い戻しはほぼ一巡、ここから先は新しい買い材料が要る）を、水準が変わった日だけ1行添える。
  半導体側では集めず、再計算もしない（数字を1か所にそろえる。定義は market-data の `08_Addendum_v4.7_Flows_Fuel_VolTerm.txt`）。
  配信でも省かない。
- 不安の指数の期間構造：signals.json の `vol_term`（`vix_over_vix3m`、`state_ja`、`last_inverted_date`、`unwinding`）を1句
  （例「VIX÷VIX3M 0.97。11/6 まで逆転、いまは解けてヘッジ外しが進んだ形」）。
  `vol_term` が無い・`vix3m` が null の日は書かない。
- これらは環境認識であり、売買の指示・週次スコアの変更には使わない。
