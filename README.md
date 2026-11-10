# semis-data

半導体・メモリー定点観測レポートのための、データ自動取得（GitHub Actions）と、2段階プロンプト（収集→判定）の置き場です。
データの取得・計算は `market-data`（米国株指標チェック用）とは独立しています。
ただし日次・週次のレポートは、`market-data` の data ブランチの `signals.json` から、市場全体のTapeレジーム・指数の崩れガード、
テック内部（IT＋通信で高値から−20%以上の銘柄比率と隠れ弱気のラベル）、ブレイクの伸び、先導セクターの推移・ヘッジ条件・長期SPY配分モデルを転記します（daily.md 6b節、judge.md 4c節と反転リスク）。
定義は market-data の `04_Addendum_v4.4_Breadth_FollowThrough.txt` と `06_Addendum_v4.5_Leadership_Hedge_SPYModel.txt`。

## 全体の流れ

1. **data ブランチ（自動）**：日本時間 火〜土の 6:35 と 12:35 に `update-semis-data` が走り、終値・テクニカル・モメンタム段階・セクターの状態・ADRプレミアム・金利と、40社の四半期実績（売上・在庫・設備投資。Yahoo の四半期財務。SEC に届く環境なら米国籍37社を XBRL で）を更新する。前営業日の足が入るまで10分おきに最大6回取り直す（Yahooが米国東部 20:30〜21:20 ごろに終値を空欄で返す時間帯への対策）。日次レポート（7:21。再試行 9:21・12:21）はデータが古ければ自分で起動する（`refresh/request.txt` を main に push すると `update-semis-data` が動く）
2. **第1段階 収集**（`prompts/collector.md`）：機械取得の実績値（`fundamentals_latest.json`）を転記し、判断に効く数字は SEC の XBRL API で確認して格上げし、ガイダンス等を IR から取り、残りをWeb検索で集めて `# SEMI_EVIDENCE` のYAMLを出す → `evidence/`。一次資料が開けないときは主要報道2本以上の一致で「報道値」として採用し、翌週以降に突き合わせる
3. **第2段階 判定**（`prompts/judge.md`）：証拠YAML＋dataブランチ＋前回引継ぎから採点・シナリオ・予測・レポートを書く → `handoff/`

収集と判定を分けるのは、判定の文脈に検索結果を入れないため（ルールの読み飛ばしを防ぐ）と、事実の記録を残すためです。

## data ブランチのファイル

| ファイル | 中身 |
|---|---|
| `run_status.json` | 直近の実行で各ステップ（prices・macro・fundamentals・snapshot・health・rebound・signals）が成功したか。failure のファイルは前回のまま |
| `prices_manifest.json` | 価格を取得した時刻（`generated_utc`）、基準日、取得できなかった銘柄。米国の取引時間中に動いた回は、当日分の未確定の足を捨て、その行数を `unclosed_dropped` に書く（基準日は前の取引日になる。2026-11-10） |
| `semis_manifest.json` | 最初に読む。基準日 `us_as_of`、欠損、品質フラグ、S/Dスコア、騰落の広がり、ADR要約、マクロ最新値 |
| `levels.json` | モメンタムの段階 S1〜S5・D1〜D6（−2〜+2）と入力値、S/D/TECHNICAL スコア |
| `semis_snapshot.csv` | 銘柄ごとの最新テクニカル指標 |
| `daily_signals.json` | 日次シグナル：前営業日との比較で検出した変化点（SMAクロス、RSI、高安更新、出来高、段階変更、ADR、VIX、金利、RS線）、主要銘柄の表、意識される水準、RS線の一覧（rs_lines：対SPY・対QQQ、52週新高値、株価に先行、21日EMA） |
| `resilience.json` | セクター内の強弱（sector_rs）と調整耐性（window、next_candidates、late_breaks） |
| `sector_health.json` | セクターの状態（config 1.6）：半導体約40銘柄の中身（簡易ステージの分布・平均線の上の割合）と判定ラベル、大きく下げる危険の目安（3条件のそろい数）、底の目安（売られ尽くし3条件のそろい数）、相対力の帯（SOXX 対 市場・テック全体・ソフト・ハード、短期・中期）、分野別。定義と15年の検証は `docs/sector_health.md`。採点には使わない |
| `history_health.csv` | セクターの状態の日次履歴（ラベル、割合、そろい数、帯の緑の数） |
| `history_key.csv` / `history_levels.csv` | 主要銘柄の指標と段階の日次履歴（前回比の計算用） |
| `adr_premium.csv` | SK hynix ADS（SKHY）の理論価値とプレミアム（直近60営業日） |
| `macro_daily.csv` | FRED：DGS10、DFII10、DTWEXBGS。参考として BAMLH0A0HYM2（HYスプレッド）・BAMLH0A3HYC（CCC格）も取る（取れなくても status は変えず `macro_manifest.json` の optional_failed に書く） |
| `fundamentals_latest.json` | 40社（米国籍37社＋TSM・ASML・ARM）の直近四半期の売上・売上原価・在庫（在庫日数）・設備投資・営業CF と前年比・前期比、ハイパースケーラー4社の設備投資合計。通常は Yahoo の四半期財務（非公式）＋ SEC の XBRL で確認するためのURL。SEC に届く環境で動いた日は SEC の値と決算リリースのURL |
| `fundamentals.csv` | 同じ項目の全期間（四半期ごと1行。`source` 列が yahoo か sec_xbrl。`derived=true` は年初来累計の差分で作った値） |
| `prices_daily.csv.gz` | 全銘柄の日足（約3年） |
| `rebound_quality.json` / `history_rebound.csv` | 戻りの質（追補 R1、2026-11-10）：S&P500・QQQ・SOX と半導体約40銘柄・メモリーの前日比と売買代金の比（50日平均／5日平均／投げ売りの日）、下げ幅のうち戻した割合、売られた銘柄ほど上げたか、レバレッジETF（SOXL・SOXS）の過熱。描写専用で採点・シグナルには使わない。定義と検証は `docs/rebound_quality.md`。失敗した日は前回のまま（`us_as_of` で確認） |

生ファイルのURL：`https://raw.githubusercontent.com/bakaho19920625-wq/semis-data/data/<ファイル名>`

## main ブランチのファイル

- `tickers.txt` … 取得する銘柄（編集するだけで追加・削除できる）。2026-11-05 に川下5銘柄（CRWV・NBIS・IREN・GLXY・VRT）を参考枠として追加。2026-11-10 に相対力の帯の比較相手（XLK・IGV とハード10銘柄）を追加（config 1.6 の `rs_benchmarks`・`hardware_basket`。採点・広がり・区分・RS線・日次シグナルには入らない）
- `config.json` … グループ、ベンチマーク、広がりの銘柄集合、ADR比率、段階の閾値、配点、SEC で取る会社と CIK（`fundamentals`）。`groups.downstream`（config 1.5）は川下の参考枠で、採点・広がり・セクター内区分・日次シグナルには入らない（daily_signals.json の `downstream` 表だけ）
- `fetch_prices.py` / `fetch_macro.py` / `fetch_fundamentals.py` / `build_snapshot.py` / `build_health.py` / `build_rebound.py` / `build_signals.py` … 取得と計算（指標の定義は build_snapshot.py、セクターの状態は build_health.py、シグナルの定義は build_signals.py の先頭、SEC の取り方と注意は fetch_fundamentals.py の先頭）
- `history/` と `.github/workflows/fetch_history.yml` … 長期検証用。手動実行（`gh workflow run fetch_history.yml`）で 106銘柄の最長の日足を取り、`history` ブランチに置く（毎日の更新とは別。閾値を見直すときの再検証に使う）
- `prompts/collector.md` / `prompts/judge.md` … 週次の2段階プロンプト（2026-11-10 時点で収集 v7.3・判定 v6.9。日次は `prompts/daily.md` v2.0）。2026-11-05（収集 v7.2・判定 v6.6）から「AIインフラの稼働タイミング」（米国内の DC 規制・許認可の状態、追跡案件 ORCL・CRWV・NBIS・IREN・GLXY の受電・引き渡し・課金開始の予定、資金調達の条件、半導体への伝わり方）を証拠YAMLの `DC_TIMING` に集め、A4・A5 の採点と反転リスク「米国内のDC規制・許認可」「AI投資の資金調達・信用」、6a節、12節の政策日程表に使う
- `prompts/daily.md` … 日次レポートのプロンプト（daily_signals.json を読み、重要ニュースを少数確認して短く書く）
- `prompts/schedule_daily.md` / `prompts/schedule_weekly.md` … 定期実行（スケジュールタスク。火〜土 7:21（データ未更新なら 9:21 に再試行）、土 10:11 JST。米国株側の日次 7:07 の後。新しいセッションで動く）の段取り。定期実行の本文はこれを読む指示だけにし、手順はここで直す
- `docs/sources.md` … 収集プロンプトが最初に1回読む情報源マップ。`docs/universe_kpi.md` … 必要なときだけ読む参照資料。`docs/sector_rs_resilience.md` … セクター内の強弱と調整耐性の定義
- `docs/plain_language.md` … やさしい表記の対応表（段階・スコア・小項目・判定の語を日本語に。日次・週次の書き方の約束）。`docs/sector_health.md` … セクターの状態の定義と15年の検証結果（乗り換え戦略が負けた記録を含む）
- `handoff/` … レポート間の引継ぎ（latest.yaml、日付別の控え、予測台帳 forecasts.csv）
- `evidence/` … 証拠YAMLの控え

## 仕組みの要点

- 前回の data ブランチを復元してから取得するので、失敗したステップのファイルは前回のまま残る
- 価格取得に失敗した日はジョブが赤になりメールが届く
- `SKHY` のADS比率（1 ADS＝普通株0.1株）は `config.json` に固定。理論値との乖離が5日続けて15%を超えると `adr_ratio_or_data_suspect` フラグが立つ

## 注意

- データ元は Yahoo の非公式な取得方法のため、まれに失敗する日がある
- 公開リポジトリのため、個人の保有情報などは置かない。SEC への名乗り（User-Agent）は GitHub の noreply アドレスを既定にし、変えるときは Secret `SEC_USER_AGENT` に置く（ファイルには書かない）
- GitHub Actions（クラウドのIP）からは SEC EDGAR が 403 で拒否される（2026-11-02 確認）。そのため四半期実績の機械取得は Yahoo で行い、SEC は収集エージェントが確認に使う。SEC に届く環境（自前のVM等）で `python fetch_fundamentals.py --source sec` を動かせば SEC の値に切り替わる
- SEC の XBRL には決算発表（8-K）の数字は入らず、10-Q/10-K の受理後（発表の当日〜2週間後）に反映される。Yahoo の値も決算直後は未反映のことがある
