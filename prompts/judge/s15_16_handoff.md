# 週次（判定）｜15. 読み方、16. 引継ぎ
# prompts/judge.md の「ひな形」の表から、この節を書く直前に読む。

- 見出し：`## 15. 読み方`、`## 16. 引継ぎ`
- このレポートで使った記号だけを対応表から1行ずつ（16節のYAMLの前に置く）
- YAMLのコードブロックを1つだけ置き、その後に文章を付けない

## 引継ぎテンプレート（空欄は埋め、なければ「未確認」「N/A」）
```yaml
# SEMI_HANDOFF
PROMPT_VERSION: v6.9
AS_OF: {market: YYYY-MM-DD, report_check: "YYYY-MM-DD HH:MM JST"}
PREVIOUS_REPORT: 前回のAS_OF または 前回基準未確認
DATA: {github_us_as_of: , run_status: , missing: [], web_fallback: [], notes: }
VIEW: {semiconductor: , memory: }
SCORES:
  total: {score: , band: "xx-xx", change_vs_prev: }
  category: {ai: /20, memory: /25, foundry_equipment: /20, earnings_valuation: /10, technical: /10, macro: /15}
  sub: {ai_infra: , memory_cycle: , foundry_equipment: , earnings_valuation: , macro: , sox_momentum: , memory_equity_momentum: , technical: }
  drivers: []
LEVELS:
  A: {A1: , A2: , A3: , A4: , A5: , A6: }
  M: {M1: , M2: , M3: , M4: , M5: , M6: }
  F: {F1: , F2: , F3: }
  E: {E1: , E2: , E3: }
  X: {X1: , X2: , X3: , X4: }
  S: {S1: , S2: , S3: , S4: , S5: }
  D: {D1: , D2: , D3: , D4: , D5: , D6: }
EVIDENCE_CONFIDENCE:
REGIME:
KEY_CHANGE:
SIGNALS:
  {AI_CAPEX: , TSMC_FOUNDRY: , EQUIPMENT: , ADVANCED_PACKAGING: , HBM: , COMMODITY_DRAM: , LEGACY_DRAM: ,
   NAND_TLC: , NAND_QLC: , NAND_ESSD: , HBF_SCM: , MEMORY_CAPEX_QUALITY: , INVENTORY: ,
   OPTICAL_MEMORY_TIERING: , SRAM_ARCHITECTURE: , AI_EFFICIENCY: , KOREA_MARKET_STRUCTURE: }
DRAM_ETF: {signal: , holdings_as_of: , nav_premium: , limitation: }
SKHY_ADR: {premium_pct: , avg20: , ratio_verified: , signal: }
SECTOR_RS: {bench: SOXX, leaders: [], laggards: [], flips: []}
CORRECTION: {bench: SOXX, state: , high: , low: , dd_low: , dd_now: , next_candidates: [], late_breaks: []}
MARKET_CONTEXT: {source_as_of: , definition_version: , tape_regime: , ix3_guard: , megacap_led: , tech_pct_down20: , tech_label: , ex_tech_pct_down20: , sp500_pct_down20: , sp500_label: , fb1_d5_hold: , fb1_d5_ret: , fb1_d10_ret: , fb1_stalling: , reversal_status: ,
  top_sectors: [], leaders_market: , leaders_market_4w: , leaders_tech: , leaders_tech_4w: , leaders_semi: , hedge_allowed: , hedge_status: , spy_model_pct: , spy_model_signal: , spy_model_since: }
FUNDAMENTAL_LEVELS: []
DC_TIMING:             # （v6.6）6a節の要約。A4・A5 と反転リスク2項目の根拠
  regulation_state:    # 継続|条件付き再開|解除|未確認
  states_with_pause:   # 停止・新規制を出した州の数
  governor_action_scope:   # 既存許可|建設中|増設 のどれを含むか（就任前は「未就任」）
  projects: []         # {company, project, stage, energization_eta, delivery_eta, billing_eta, shift_vs_prev, status_change}
  projects_delayed:    # 後ろ倒しの件数（決算で確認したもの）
  financing_signal:    # 同水準|厳しい|緩い（新規調達の条件）
  gpu_rental_signal:   # 上昇|横ばい|下落|未確認（貸す側の追い風。採点には使わない）
  passthrough_signal:  # 後ろ倒し発言の社数と影響地域数
  scenario_lean:       # 楽観|基本|悲観
FLOWS_CREDIT:          # （追補 R1）10a節の転記。表示のみ（採点には入れない）
  fuel: {week_ending: , remaining_pct: , level: , hf_net_pctile: , discretionary_pctile: , systematic_pctile: , cta_next_week_usd_bn: , buyback_open_pct: , source_updated: }
  market_credit: []    # {issuer, instrument, value, unit, as_of, status}
  hy_oas: {value_pct: , date: , chg_21obs: }
  ccc_oas: {value_pct: , date: , chg_21obs: }
  construction: {month: , saar_usd_bn: , yoy_pct: }
DOWNSTREAM_RS: []      # 川下5銘柄 {ticker, close, ret_1w, rs_soxx_20, rs_soxx_60, dd_from_high}（semis_snapshot.csv の downstream。参考枠）
SECTOR_HEALTH:         # （v6.7）4d節の転記。sector_health.json の値そのまま（再計算しない）。採点には入れない
  {as_of: , health_version: , label: , label_prev: , official_label: , official_pct_stage: {}, soxx_stage: , smh_stage: ,
   breadth: {stage2: , stage4: , above20: , above50: , above150: , net: }, risk_count: , risk_conditions_met: [], washout_count: , washout_conditions_met: [], washout_last_all3: ,
   washout_phase: {code: , ja: , anchor_date: , anchor_close: , close_vs_anchor_pct: , retest_line: , breakdown_line: , low_since_anchor_pct: , relit_dates: [], recovery_confirmed_date: },   # v6.8
   strip: {ema21: {green: , of: , state: , since: }, ema50: {green: , of: , state: , since: , all_red_days: , all_green_days: }}, benches_missing: [],
   subsectors_strongest: , subsectors_weakest: }
FORECASTS: {open: [], new: [], resolved: []}
TRACK_RECORD: {hit: , miss: , void: , brier_avg: }
REVERSAL_RISKS: {triggered: [], warning: []}   # 「米国内のDC規制・許認可」「AI投資の資金調達・信用」の状態も必ずどちらかに入れるか、本文10節で未発動と書く
SCENARIOS:
  "0-3M": {bull: , base: , bear: , base_case: }
  "3-12M": {bull: , base: , bear: , base_case: }
  "1-3Y": {bull: , base: , bear: , base_case: }
TOP_UPSIDE_TRIGGER:
TOP_DOWNSIDE_TRIGGER:
THESIS_INVALIDATION:
NEXT_CHECKPOINTS: []
UNCONFIRMED_ITEMS: []
PRIMARY_SOURCES: []
```
