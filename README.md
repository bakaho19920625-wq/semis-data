# semis-data

半導体・メモリー定点観測レポート用のデータを、GitHub Actions で毎日自動取得するリポジトリです。
`market-data`（米国株指標チェック用）とは独立しています。

## 毎朝つくられるもの（data ブランチ）

| ファイル | 中身 |
|---|---|
| `semis_manifest.json` | 最初に読む。基準日、欠損銘柄、品質フラグ、S/Dスコア、騰落の広がり、ADR要約、マクロ最新値 |
| `levels.json` | モメンタムの段階 S1〜S5・D1〜D6（−2〜+2）と入力値、S/D/TECHNICAL スコア |
| `semis_snapshot.csv` | 銘柄ごとの最新テクニカル指標（1行1銘柄） |
| `adr_premium.csv` | SK hynix ADS（SKHY）の理論価値とプレミアム（直近60営業日） |
| `macro_daily.csv` | FRED：DGS10（10年名目）、DFII10（10年実質）、DTWEXBGS（ドル指数） |
| `history_levels.csv` | 段階・スコアの日次履歴 |
| `history_key.csv` | 主要銘柄の終値・SMA・RSI等の日次履歴（前回比の計算用） |
| `prices_daily.csv.gz` | 全銘柄の日足（約3年） |
| `run_status.json` | 今回の実行で各ステップが成功したか |

生ファイルのURL（例）: `https://raw.githubusercontent.com/<ユーザー名>/semis-data/data/semis_manifest.json`

## 仕組み

- 平日 22:27 UTC（日本時間の火〜土 7:27）に `update-semis-data` が動く
- 前回の data ブランチを復元してから取得するので、失敗したステップのファイルは前回のまま残る
- 各ステップの成否は `run_status.json` に記録される。価格取得に失敗した日はジョブが赤になりメールが届く
- 指標の定義は `build_snapshot.py` の先頭、段階の閾値は `config.json` の `levels` にある

## ファイル

- `tickers.txt` … 取得する銘柄（編集するだけで追加・削除できる）
- `config.json` … グループ、ベンチマーク、広がりの銘柄集合、ADR比率、段階の閾値、配点
- `fetch_prices.py` … Yahoo Finance から日足を取得
- `fetch_macro.py` … FRED から金利・ドル指数を取得
- `build_snapshot.py` … 指標・段階・履歴を計算
- `handoff/` … レポート間の引継ぎ（main ブランチ。詳細は handoff/README.md）

## 注意

- データ元は Yahoo の非公式な取得方法のため、まれに失敗する日がある
- `SKHY` のADS比率（1 ADS＝普通株0.1株）は `config.json` に固定している。変更があれば更新する
- 公開リポジトリのため、個人の保有情報などは置かない
