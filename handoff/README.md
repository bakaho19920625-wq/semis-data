# handoff（レポート間の引継ぎ）

- `latest.yaml` … 直近レポートの引継ぎ（`# SEMI_HANDOFF` で始まるYAML）。レポートのたびに上書きする
- `YYYY-MM-DD.yaml` … 各回の引継ぎの控え
- `forecasts.csv` … 予測の台帳。1行1予測。status は open / hit / miss / void
  - brier は判定時に (probability/100 − result)^2 を書く（hit=1、miss=0、void は空欄）

このフォルダは main ブランチにあります（data ブランチは自動更新専用で、手で触りません）。
Claude がリポジトリに書き込めない環境で実行した場合は、レポート末尾のYAMLを
GitHubの画面で `handoff/latest.yaml` に貼り付けて保存してください。
