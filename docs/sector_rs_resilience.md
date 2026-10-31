# 半導体・メモリー定点観測｜追加仕様 v6.1「セクター内RS」「調整耐性」

定義の正本は米国株指標チェック側の追補（E7.1 セクター相対強度、E7.2 調整耐性）：
`https://raw.githubusercontent.com/bakaho19920625-wq/market-data/main/03_Addendum_v4.3_SectorRS_Resilience.txt`
本ファイルは、この観測で使うパラメータ、データの出力先、プロンプトとの対応だけを書く。
実装：build_snapshot.py（`sector_rs_and_resilience`）、build_signals.py。設定：config.json の `sector_rs`・`resilience`。
作成 2026-10-31（DEFINITIONS 1.2、config 1.3、判定プロンプト v6.1、日次プロンプト v1.1）。

## 0. 位置づけ

- 目的1：半導体約40銘柄＋米国メモリー株を、SOXXと比べて「リーダー／中立／ラガード」に機械的に分ける。
  S4（SOXXの対SPY相対強度）は「セクターが市場より強いか」、本項は「銘柄がセクターより強いか」。別物として扱う。
- 目的2：SOXXが調整している間に崩れなかった銘柄・戻りで先行した銘柄をリストにし、週次・日次で保持する。
- 採点（S1〜S5、D1〜D6、A〜X、重み）は変えない。表示項目・引継ぎ項目・変化点シグナルの追加だけ。
- 判定プロンプトは v6 → v6.1。採点定義の変更がないので「定義変更あり」にせず、前回比はそのまま有効（judge.md 入力1 に明記）。

## 1. パラメータ（config.json）

| 項目 | 値 | 備考 |
|---|---|---|
| 基準ETF | SOXX のみ | 市場（SPY）版は作らない。S4で足りる |
| 相対強度の本数 | 20本・60本 | 既存の `rs_soxx_20`・`rs_soxx_60` をそのまま使う（正本は21・63）。式はリターン差（%ポイント）で、正本の比率式と符号は同じ |
| 対象銘柄 | `breadth_sets.semis_broad` ∪ `groups.memory_us`（MU、SNDK、SKHY、WDC、STX） | アジア株（.KS .T .TW）は時差があるため対象外。DRAM、SOXL、指数・ETFも対象外。42銘柄 |
| 調整窓の成立 | dd_low ≦ −5%、T_high→T_low 5本以上 | −5〜−8%は「浅い調整（参考）」 |
| 区分の閾値 | 耐えた ≦0.5、同調 ≦1.0、崩れた >1.0（下げ耐性比）／先行 ≦0.5、同調 ≦1.0、遅れ >1.0（戻り比） | 正本と同じ |
| 新高値の格上げ | 安値後に52週終値高値を更新し、いまも高値から−15%以内なら 同調→先行 | 何か月も前に新高値を付けてから崩れた銘柄を先行にしないため |
| 完了した調整の保持 | 新高値回復から60本以内 | 正本と同じ |
| 履歴の下限 | 窓開始前に120本 | 足りなければ下げ耐性は N/A（SKHY は2026-07-09上場のため当面 N/A） |

定義の要約（詳細は正本）：
- セクター内区分：`rs_soxx_20 > 0` かつ `rs_soxx_60 > 0` かつ `dd_vs_soxx_pt > 0` → leader、3つとも負 → laggard、それ以外 → neutral。
  `dd_vs_soxx_pt` ＝ 銘柄の `dd_from_high` − SOXXの `dd_from_high`（%pt。どちらも終値ベース）。`rs_soxx_line_60h` ＝ P/SOXX が直近60本の高値以上。
- 調整窓：SOXXの直近252本の終値最高値の日 T_high → 以降の最安値の日 T_low。
  状態＝調整中（dd_now≦−5%）／回復中／完了（直前：現在の窓が未成立で、直近60本以内に新高値で回復した調整がある）／なし。
- 下げ耐性比 R_held ＝（窓内で銘柄が自分の高値から下げた率）÷（SOXXの dd_low）。銘柄の高値は「T_high時点の52週終値高値と窓内最高値の大きい方」。
- 戻り比 R_now ＝ 銘柄の高値からの下落率 ÷ SOXXの dd_now（SOXXが高値から−2%以内ならN/A。そのときは自分の高値距離で −5%以内＝先行、−10%以下＝遅れ）。
- 次の候補：A＝耐えた∧（先行∨同調）、B＝同調∧先行、C＝崩れた∧先行。後崩れ＝（耐えた∨同調）∧遅れ。

## 2. データの出力先（data ブランチ）

- `semis_snapshot.csv` 追加列（対象銘柄だけ値が入る）：`dd_vs_soxx_pt`、`sector_rs_class`、`rs_soxx_line_60h`、
  `own_dd_low_pct`、`r_held`、`held_class`、`own_dd_now_pct`、`r_now`、`rebound_class`、`new_high_after_low`、`below_50sma_days`、`tier`、`late_break`。
- `resilience.json`（新規）：
  `us_as_of`、`definition_version`、`sector_rs`{bench、windows、targets、counts、leaders（rs_soxx_60降順）、laggards（昇順）、classes}、
  `window`{bench、state、valid、high_date、low_date、dd_low_pct、dd_now_pct、bars_high_to_low、bars_since_low、note}、
  `rows`（対象銘柄ごとの全指標）、`next_candidates`（A→B→C、各枠内 r_held 昇順）、`late_breaks`、`held_ratio`、`note`。
- `semis_manifest.json`：`files` に resilience.json、`resilience` に要約（state、dd、次の候補、後崩れ、リーダー／ラガード上位5）。
- `history_levels.csv` 追加列：`corr_state`、`corr_dd_now`、`held_ratio_pct`、`next_candidates`、`sector_leaders`、`sector_laggards`（採点には使わない）。
- `daily_signals.json`（build_signals.py）：
  - `signals` に追加：`sector_rs_flip`（leader⇄laggard、medium）、`next_candidate_new`／`next_candidate_out`（medium）、`late_break_new`（high）、`corr_state_change`（high）。
    前営業日の値は日足から再計算して比べる（既存のシグナルと同じ方式。状態ファイル不要）。
  - `sector_rs`（counts、leaders、laggards、leaders_top5、laggards_bottom5）、`resilience`（window、held_ratio、next_candidates 上位8、late_breaks）。

## 3. プロンプトとの対応

- judge.md（v6.1）：入力3に resilience.json、共通ルールに混同禁止、出力形式 4a「セクター内の強弱」・4b「調整耐性」、引継ぎYAMLに `SECTOR_RS`・`CORRECTION` の2行、自己点検 C7。
- daily.md（v1.1）：入力1に sector_rs／resilience、出力 4b「セクター内の強弱と調整耐性（3行以内）」、禁止事項に売買判断の禁止。
- どちらも値は転記のみ。再計算しない。採点に使わない。

## 4. 実行結果（2026-10-30終値。build_snapshot.py v6.1 の出力。レポートに転記しない）

- SOXX：T_high 2026-06-22、T_low 2026-07-29、dd_low −29.0%、dd_now −28.0%（10/30に−7.2%）、状態＝調整中。耐えた＝0/41。
- セクター内区分：leader 13（SWKS、SNPS、NXPI、ADI、ENTG、TXN、ASX、MCHP、MU、TSM、CDNS、NVDA、ASML）、neutral 10、laggard 19（COHR、SITM、CRDO、INTC、TER、ARM、LSCC、AMKR、AMAT、ONTO ほか）。
  MU が leader なのは、10/30のSOXX急落で相対的に浅い下げ（dd −27.1% vs SOXX −28.0%）になり、20本・60本の対SOXXが両方プラスのため。急落日は区分が動きやすい。
- 次の候補：B＝TXN（R_held 0.63、R_now 0.34）、NVDA（0.67、0.52、新高値で格上げ）、ADI（0.71、0.23）。C＝SWKS（新高値、高値から−4.2%）、SNPS（R_now 0.45）。
  10/29→10/30 のシグナル：TSM・AMD・ASX が「次の候補から外れた」（SOXX急落で戻り比が0.5を超えた）。
- 後崩れ：LSCC（0.94→1.43）、AVGO（0.87→1.15）、MPWR（0.90→1.01）。
- メモリー：MU は崩れた（1.35）×同調（0.97）、区分 leader。SNDK は崩れた（1.95）×遅れ（1.81）。WDC・STX は崩れた×遅れ。SKHY は履歴不足で下げ耐性 N/A（区分は neutral）。
