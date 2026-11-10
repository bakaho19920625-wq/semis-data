# 4b. セクター内の強弱と調整耐性

- 見出し：`### 4b. セクター内の強弱と調整耐性`
- 分量：3行以内。
- 短縮形（「前日から変わった点」に、この節に関わる変化が無い日）：1行（リーダー上位3、ラガード下位3、次の候補の上位3）。
リーダー上位3・ラガード下位3（`sector_rs.leaders_top5`／`laggards_bottom5` から。対SOXX 60本）。
SOXXの調整窓の状態を1行（`resilience.window`：state、dd_low、dd_now）。
次の候補の上位5（tier、下げ耐性×戻り、R_held、R_now）と後崩れ（`resilience.next_candidates`／`late_breaks` から転記）。
`sector_rs_flip`・`next_candidate_new`・`next_candidate_out`・`late_break_new`・`corr_state_change` は1節のシグナルに含まれるので、ここでは再掲しない。
