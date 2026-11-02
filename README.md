# semis-data

半導体・メモリー定点観測レポートのための、データ自動取得（GitHub Actions）と、2段階プロンプト（収集→判定）の置き場です。
データの取得・計算は `market-data`（米国株指標チェック用）とは独立しています。
ただし日次・週次のレポートは、`market-data` の data ブランチの `signals.json` から、市場全体のTapeレジーム・指数の崩れガード、
テック内部（IT＋通信で高値から−20%以上の銘柄比率と隠れ弱気のラベル）、ブレイクの伸び、先導セクターの推移・ヘッジ条件・長期SPY配分モデルを転記します（daily.md 6b節、judge.md 4c節と反転リスク）。
定義は market-data の `04_Addendum_v4.4_Breadth_FollowThrough.txt` と `06_Addendum_v4.5_Leadership_Hedge_SPYModel.txt`。

## 全体の流れ

1. **data ブランチ（自動）**：日本時間 火〜土の 6:35 と 12:35 に `update-semis-data` が走り、終値・テクニカル・モメンタム段階・ADRプレミアム・金利と、40社の四半期実績（売上・在庫・設備投資。Yahoo の四半期財務。SEC に届く環境なら XBRL）を更新する。前営業日の足が入るまで10分おきに最大6回取り直す（Yahooが米国東部 20:30〜21:20 ごろに終値を空欄で返す時間帯への対策）。日次レポート（8:53）はデータが古ければ手動起動する
2. **第1段階 収集**（`prompts/collector.md`）：機械取得の実績値（`fundamentals_latest.json`）を転記し、判断に効く数字は SEC の XBRL API で確認して格上げし、ガイダンス等を IR から取り、残りをWeb検索で集めて `# SEMI_EVIDENCE` のYAMLを出す → `evidence/`。一次資料が開けないときは主要報道2本以上の一致で「報道値」として採用し、翌週以降に突き合わせる
3. **第2段階 判定**（`prompts/judge.md`）：証拠YAML＋dataブランチ＋前回引継ぎから採点・シナリオ・予測・レポートを書く → `handoff/`

収集と判定を分けるのは、判定の文脈に検索結果を入れないため（ルールの読み飛ばしを防ぐ）と、事実の記録を残すためです。

## data ブランチのファイル

| ファイル | 中身 |
|---|---|
| `run_status.json` | 直近の実行で各ステップが成功したか。failure のファイルは前回のまま |
| `semis_manifest.json` | 最初に読む。基準日 `us_as_of`、欠損、品質フラグ、S/Dスコア、騰落の広がり、ADR要約、マクロ最新値 |
| `levels.json` | モメンタムの段階 S1〜S5・D1〜D6（−2〜+2）と入力値、S/D/TECHNICAL スコア |
| `semis_snapshot.csv` | 銘柄ごとの最新テクニカル指標 |
| `daily_signals.json` | 日次シグナル：前営業日との比較で検出した変化点（SMAクロス、RSI、高安更新、出来高、段階変更、ADR、VIX、金利、RS線）、主要銘柄の表、意識される水準、RS線の一覧（rs_lines：対SPY・対QQQ、52週新高値、株価に先行、21日EMA） |
| `history_key.csv` / `history_levels.csv` | 主要銘柄の指標と段階の日次履歴（前回比の計算用） |
| `adr_premium.csv` | SK hynix ADS（SKHY）の理論価値とプレミアム（直近60営業日） |
| `macro_daily.csv` | FRED：DGS10、DFII10、DTWEXBGS |
| `fundamentals_latest.json` | 40社（米国籍37社＋TSM・ASML・ARM）の直近四半期の売上・売上原価・在庫（在庫日数）・設備投資・営業CF と前年比・前期比、ハイパースケーラー4社の設備投資合計。通常は Yahoo の四半期財務（非公式）＋ SEC の XBRL で確認するためのURL。SEC に届く環境で動いた日は SEC の値と決算リリースのURL |
| `fundamentals.csv` | 同じ項目の全期間（四半期ごと1行。`source` 列が yahoo か sec_xbrl。`derived=true` は年初来累計の差分で作った値） |
| `prices_daily.csv.gz` | 全銘柄の日足（約3年） |

生ファイルのURL：`https://raw.githubusercontent.com/bakaho19920625-wq/semis-data/data/<ファイル名>`

## main ブランチのファイル

- `tickers.txt` … 取得する銘柄（編集するだけで追加・削除できる）
- `config.json` … グループ、ベンチマーク、広がりの銘柄集合、ADR比率、段階の閾値、配点、SEC で取る会社と CIK（`fundamentals`）
- `fetch_prices.py` / `fetch_macro.py` / `fetch_fundamentals.py` / `build_snapshot.py` / `build_signals.py` … 取得と計算（指標の定義は build_snapshot.py、シグナルの定義は build_signals.py の先頭、SEC の取り方と注意は fetch_fundamentals.py の先頭）
- `prompts/collector.md` / `prompts/judge.md` … 週次の2段階プロンプト
- `prompts/daily.md` … 日次レポートのプロンプト（daily_signals.json を読み、重要ニュースを少数確認して短く書く）
- `prompts/schedule_daily.md` / `prompts/schedule_weekly.md` … 定期実行（スケジュールタスク。火〜土 8:53、土 10:11 JST。新しいセッションで動く）の段取り。定期実行の本文はこれを読む指示だけにし、手順はここで直す
- `docs/sources.md` / `docs/universe_kpi.md` … 収集時に必要なときだけ読む参照資料
- `docs/plain_language.md` … やさしい表記の対応表（段階・スコア・小項目・判定の語を日本語に。日次・週次の書き方の約束）
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
