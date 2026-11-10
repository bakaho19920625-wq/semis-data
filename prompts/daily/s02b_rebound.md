# 2b. 戻りの質

- 見出し：`#### 2b. 戻りの質`
- data ブランチ `rebound_quality.json` から転記する。再計算しない。定義・言葉・検証は docs/rebound_quality.md。
大きく下げた後の上げが「売りすぎた人の買い戻し中心」か「新しい買いが入っている」かを、値動きと売買代金で描写する。
2節（解釈）の一部として書く。
配信（schedule_daily.md 第9節）には、この節の最後の1行を入れる。
この節の表は「表は5つまで」（daily.md の進め方）に数えない。
- 出す日：`context.in_correction` が真（SOXX が高値から−10%以下）の日は、上げた日も下げた日も出す。
  偽の日は「戻りの質：調整局面ではないため省略（SOXX は高値から○%）」の1行。
  ファイルが無い、`status` が ok でない、`us_as_of` が今日の基準日と違う日は「戻りの質：未取得」の1行（data ブランチのクローン /home/claude/sd-data に入っている。無ければ raw URL）。
- 表1つ。
  行＝**S&P500、QQQ（ナスダック100）、SOX**、半導体（`semis.n` 銘柄）、メモリー（米国5銘柄）。
  列＝前日比、売買代金は50日平均の何倍か（と言葉：少ない／平均並み／多い）、5日平均の何倍か、投げ売りの日の何倍か、下げ幅のうち戻した割合（高値からの位置）。
  指数3行は `indexes` から（`ret_1d_pct`、`dv_vs_50d`＋`volume_word`、`dv_vs_5d`、`dv_vs_selloff_day`、`retrace_pct`＋`dd_now_pct`）。
  半導体は `semis`（`avg_ret_pct`、`agg_dv_vs_50d`、`agg_dv_vs_5d`、`agg_dv_vs_selloff_day`）、メモリーは `memory_us`（同じ項目。無い項目は「−」）。
  戻した割合は指数だけ。
  表の下に注を1行：「売買代金＝終値×出来高。S&P500 と SOX は指数に出来高がないので SPY・SOXX で代用。投げ売りの日＝○/○（`context.selloff_day`。無ければその列は省く）」。
- 表の後に3〜5行（`summary_ja` を土台に、数字は変えず言葉だけ整える）：
  ①幅：上げ・下げの数。
   上げた銘柄のうち、売買代金が50日平均より少ない数（`up_on_thin`）と1.5倍以上の数（`up_on_heavy`）。
   下げが多い日は下げ側（`down_on_heavy`・`down_on_thin`）
  ②売買代金の偏り：最大の1銘柄（`top_dv_ticker`、`top_dv_share_pct`）と、それを除いた合計の5日平均比（`agg_ex_top_dv_vs_5d`）
  ③主役：`laggard_lead.word` と、直前20日の騰落率が下位・上位3分の1の銘柄の今日の平均、順位相関
  ④メモリー：`memory_us.rows` の銘柄ごとの前日比と売買代金の比
  ⑤レバレッジETF：`leveraged` の SOXL・SOXS（売買代金、50日平均の何倍か、手元の期間で何番目か）と、（SOXL＋SOXS）÷SOXX（`combined_vs_base`）。
   SOXS が missing の間は SOXL だけ書く
- 最後に1行：0節の底の局面（`washout.phase`）と並べた描写。
  例「売られ尽くした後の反発2日目。今日の上げは投げ売りの日より売買代金がずっと少なく、売られた銘柄ほど上げた（買い戻しが中心の日に出やすい形）」。
  予測は書かない（docs/rebound_quality.md 4節：約3年の18回では、この指標だけでその後の上げ下げは分けられなかった）。
- 「出来高を伴って全面高」と書いてよいのは、`semis.up_on_heavy` が `semis.up` の半分を超え、かつ `semis.agg_ex_top_dv_vs_5d` が1を超える日だけ。
  それ以外の日は「全面高だが売買代金は○○」と数字で書く（冒頭の「なぜその判断か」も同じ）。
