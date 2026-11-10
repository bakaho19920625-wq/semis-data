# 半導体・メモリー定点観測｜欠けた週の補完
# 土曜の定期実行が動かなかった週の週次を、後日作る手順。きっかけがあったときだけ読む。

- きっかけ：日次の冒頭の警告（先週の週次が未作成）か、ユーザーの「半導体の週次を補完して」。
  自動では作らない。
- 基準日 D：欠けた週の金曜（休場なら最後の取引日）。
  /home/claude/sd-data を D 時点に戻す：`cp` で作業用ディレクトリに複製し、
  `python3 build_snapshot.py --out <dir> --as-of D && python3 build_health.py --out <dir> --as-of D && python3 build_signals.py --out <dir> --as-of D`（levels.json・semis_manifest.json・daily_signals.json・resilience.json・sector_health.json が D 時点の値になる）。
  米国株側の signals.json は market-data の `analyze.py --as-of D --replay-ledger 130`（market-data の runbook/daily_backfill.txt）で D 時点の値を作る。
- 収集（schedule_weekly.md 第3節）と判定（同 第4節）は通常どおり2段階で行う。
  収集エージェントには「市場基準日は D。D より後に公表された決算・統計・報道は使わない（D 時点で分かっていたことだけ）」と伝える。
  判定エージェントには「D 時点の levels.json（複製側）に LEVELS を一致させる」「予測の期限は D 基準」と伝える。
- タイトルに「（補完版）」、0節に「この週の週次は配信できなかったため、後日 D 時点のデータで作り直したもの」と書く。
- 保存は schedule_weekly.md 第6節と同じ（commit「report D (backfill)」）。
  handoff/latest.yaml は、補完した週より新しい週次がすでにあるなら上書きしない（handoff/D.yaml だけ置く）。
  forecasts.csv には追記する。
  読む用の保管ページにも入れる（prompts/archive_page.md。補完した週が新しい4本に入らないときは、手順1を `--id D` に替えてその1本を作る）。
  配信の最後に schedule_weekly.md 第7節と同じ保管ページの1行。
