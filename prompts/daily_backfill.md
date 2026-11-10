# 半導体・メモリー定点観測｜欠けた日の補完（日次）
# 利用上限などで日次が配信できなかった日を、後日作る手順。prompts/schedule_daily.md 第5節で「欠けた日がある」と分かったときだけ読む。

- 判定の履歴（history_levels.csv、history_key.csv）は GitHub Actions が毎朝作るので欠けない。
  欠けるのはレポートと、その日の daily_signals.json（上書きされる）。
  build_snapshot.py と build_signals.py の `--as-of YYYY-MM-DD` で、その日までの足だけから levels・daily_signals を作り直せる（11/5 で検証済み：history_levels.csv の同じ日の段階と完全一致）。
- 作り方（1日分 D ごと）：
  1. `rm -rf /home/claude/sbf_D && mkdir /home/claude/sbf_D && cp /home/claude/sd-data/* /home/claude/sbf_D/`
  2. `cd /home/claude/semis-data && python3 build_snapshot.py --out /home/claude/sbf_D --as-of D && python3 build_health.py --out /home/claude/sbf_D --as-of D && python3 build_rebound.py --out /home/claude/sbf_D --as-of D && python3 build_signals.py --out /home/claude/sbf_D --as-of D`
     （数秒。daily_signals.json に backfill が入る。sector_health.json も D 時点の値になる（build_signals より前に実行する）。rebound_quality.json（戻りの質）も D 時点の値になる。macro は実行時点の最新値のまま。data ブランチには書かない）
  3. prompts/daily.md の形式で補完版を書く（schedule_daily.md 第6節と同じく書き手に任せ、下の条件を「伝えておくこと」に入れる）：入力は /home/claude/sbf_D/daily_signals.json・semis_manifest.json・semis_snapshot.csv・sector_health.json・rebound_quality.json。
     タイトルに「（補完版）」、冒頭に
     「この日の日次は配信できなかったため、後日 D までのデータで作り直したもの。シグナル・段階・水準・RS線はエンジンの再計算で当時と同じ。ニュース（7節）と Web確認は含まない。
     6b節は米国株側の history_signals.csv の D の行（regime_effective、IX3_guard、BR5_tech・ラベル、FB1_stalling、top_sectors、tech_leaders、semi_leaders、hedge_status、spy_model）から転記」と書く。
     Web確認はしない。
     7節は「補完のため省略」。
     9節（週次判定との整合）は当時の直近の週次に対して書く。
  4. 保存：reports/daily/D.md（commit「daily D (backfill)」）。
     handoff/daily_state.yaml の last_us_as_of は、補完した日より新しい日次があるなら変えない（notes に補完した旨を1行）。
     読む用の保管ページにも入れる（prompts/archive_page.md。補完した日が新しい7本に入らないときは、手順1を `--id D` に替えてその1本を作る）。
  5. 配信：SendUserMessage で冒頭ブロックと本日のシグナル（high だけ）を短く（「補完版」と明記。最後に schedule_daily.md 第9節と同じ保管ページの1行）。
     SendUserFile で本文。
- 補完は今日の日次より先に、古い日から順に。
  1日分に5分超かかるときは今日の日次を先に出し、補完は件数だけ知らせる。
- 週次が欠けたとき（土曜の定期実行が動かなかった）はここでは作らない。
  ユーザーの依頼で prompts/weekly_backfill.md に従う。
