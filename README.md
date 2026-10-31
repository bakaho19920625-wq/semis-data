# semis-data

半導体・メモリー定点観測レポートのための、データ自動取得（GitHub Actions）と、2段階プロンプト（収集→判定）の置き場です。
`market-data`（米国株指標チェック用）とは独立しています。

## 全体の流れ

1. **data ブランチ（自動）**：平日 22:27 UTC（日本時間 火〜土 7:27）に `update-semis-data` が走り、終値・テクニカル・モメンタム段階・ADRプレミアム・金利を更新する
2. **第1段階 収集**（`prompts/collector.md`）：Web検索で一次情報を集め、`# SEMI_EVIDENCE` のYAMLを出す → `evidence/`
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
| `prices_daily.csv.gz` | 全銘柄の日足（約3年） |

生ファイルのURL：`https://raw.githubusercontent.com/bakaho19920625-wq/semis-data/data/<ファイル名>`

## main ブランチのファイル

- `tickers.txt` … 取得する銘柄（編集するだけで追加・削除できる）
- `config.json` … グループ、ベンチマーク、広がりの銘柄集合、ADR比率、段階の閾値、配点
- `fetch_prices.py` / `fetch_macro.py` / `build_snapshot.py` / `build_signals.py` … 取得と計算（指標の定義は build_snapshot.py、シグナルの定義は build_signals.py の先頭）
- `prompts/collector.md` / `prompts/judge.md` … 週次の2段階プロンプト
- `prompts/daily.md` … 日次レポートのプロンプト（daily_signals.json を読み、重要ニュースを少数確認して短く書く）
- `docs/sources.md` / `docs/universe_kpi.md` … 収集時に必要なときだけ読む参照資料
- `handoff/` … レポート間の引継ぎ（latest.yaml、日付別の控え、予測台帳 forecasts.csv）
- `evidence/` … 証拠YAMLの控え

## 仕組みの要点

- 前回の data ブランチを復元してから取得するので、失敗したステップのファイルは前回のまま残る
- 価格取得に失敗した日はジョブが赤になりメールが届く
- `SKHY` のADS比率（1 ADS＝普通株0.1株）は `config.json` に固定。理論値との乖離が5日続けて15%を超えると `adr_ratio_or_data_suspect` フラグが立つ

## 注意

- データ元は Yahoo の非公式な取得方法のため、まれに失敗する日がある
- 公開リポジトリのため、個人の保有情報などは置かない
