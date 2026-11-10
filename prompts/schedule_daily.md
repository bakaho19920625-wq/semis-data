# 半導体・メモリー定点観測｜日次の定期実行 手順（schedule_daily v1.6。v1.6＝配信に底の局面（daily.md v1.8）。v1.3＝配信に川下・政策日程・反転リスク2項目を追加。v1.4＝欠けた日の補完（第5節、build_*.py --as-of）、12:21 の再試行、週次未作成の警告。v1.5＝daily.md v1.7 対応：入力・配信・補完に sector_health.json（セクターの状態）を追加、12:21 の再試行の扱いを明記）
# 定期実行（スケジュールタスク。火〜土 07:21 JST の1回目と、データ未更新や利用上限で動けなかったときの 09:21・12:21 の再試行。会話の記憶がない新しいセッションで動く）の本文は、このファイルを読む指示だけ。手順を変えるときはこのファイルを直す。
# 米国株側の日次（7:07）の後に置く：6b節で米国株側の signals.json を転記するため。
# 2026-11-02 まで「半導体チャットへの予約（send_later）」方式だったが、実行済みの予約が毎日増えるため、米国株側と同じ定期実行に変更した。
# レポートの中身・形式は prompts/daily.md が正本。ここは「準備・新しさの判定・保存・配信」の段取りだけ。

## 1. 準備
- /home/claude/semis-data がなければ add_repo（owner=bakaho19920625-wq、repo=semis-data、access=push）のあと
  `git clone --depth 1 https://github.com/bakaho19920625-wq/semis-data /home/claude/semis-data`。あれば `git -C /home/claude/semis-data pull -q`。
- data ブランチ：`rm -rf /home/claude/sd-data && git clone -q --depth 1 --branch data https://github.com/bakaho19920625-wq/semis-data.git /home/claude/sd-data`
- 米国株指標チェックの判定結果（市場全体・テック内部・ブレイクの伸び・先導セクター・ヘッジ条件・長期の目安。daily.md 6b節で転記する）：
  `curl -sSf https://raw.githubusercontent.com/bakaho19920625-wq/market-data/data/signals.json -o /home/claude/mkt_signals.json`
  届かなければ `rm -rf /home/claude/mkt-data && git clone -q --depth 1 --branch data https://github.com/bakaho19920625-wq/market-data.git /home/claude/mkt-data`
  （signals.json はその中）。取れなければ 6b節は「取得できず」。market-data 側は起動しない（更新が実行中なら daily.md 手順1 のとおり最大5分待つ）。

## 2. 実行
- /home/claude/semis-data/prompts/daily.md を読み、その手順・出力形式・禁止事項に完全に従う。
- 入力：/home/claude/sd-data/daily_signals.json、run_status.json、semis_manifest.json、semis_snapshot.csv、［v1.5］sector_health.json（daily.md 0節。無い・status が ok でない日は「未取得」の1行）、
  /home/claude/semis-data/handoff/latest.yaml、handoff/daily_state.yaml、/home/claude/mkt_signals.json（6b節と、［v1.5］0節の公式ステージ stages.etfs・stages.breadth）。Web確認は最大6回。
- ［v1.2］同じ us_as_of の日次をすでに配信済み（handoff/daily_state.yaml の last_us_as_of が今回の us_as_of と同じ、または reports/daily/<us_as_of>.md がある）なら、何も送らず終了（9:21・12:21 の再試行で前の回が成功していたとき）。
- ［v1.4］欠けた日の確認：reports/daily/ に無い米国取引日（/home/claude/sd-data/history_levels.csv の us_as_of の列が取引日の一覧）が直近にあれば、今日の日次の前に第5節の補完版を作る（最大3日分。古い順）。
- ［v1.4］直近の金曜の週次 reports/<金曜の日付>.md が無い月〜水の実行では、配信の冒頭に「先週の週次定点観測は未作成です。「半導体の週次を補完して」で作れます」と1行出す（日次の中で週次は作らない）。
- daily.md 手順1 の新しさの判定で「休場」なら、7:21 の1回目だけその1行を SendUserMessage で送って終了（9:21 では送らない）。
  「GitHubデータ未更新」なら、7:21 の1回目は何も送らず終了（9:21 の再試行に任せる）、9:21・12:21 の再試行ならその1行を送って終了（12:21 は 9:21 が利用上限で動けなかった日のため。重複して届くことがあるが、沈黙より良い）。いずれも保存しない。

## 3. 保存
- レポートを /home/claude/semis-data/reports/daily/<us_as_of>.md に書き、handoff/daily_state.yaml を更新（last_us_as_of、reported_urls、review_candidates）。
- `git add -A` → commit「daily <us_as_of>」→ `git push origin main`。data ブランチには書かない。

## 4. 配信
SendUserMessage で2〜3画面：冒頭ブロック（daily.md の「今日のひとこと」3行＋「なぜその判断か」をそのまま）、［v1.5］セクターの状態（daily.md 0節：判定ラベルと分母、危険の目安 n/3、底の目安 n/3 と底の局面（局面が none 以外なら、起点比・二番底の線・底割れの線と、過去の二番底の時期の範囲を1行）、帯の緑の数と状態。売買の合図ではない言い方で）、本日のシグナル（high→medium、全件）、解釈（daily.md 2節）、
意識される水準（SOXX・SOXL・DRAM・MU・SNDK・SKHY の終値と SMA50/200、直近20日高安）、
RS線（daily.md 6節：対SPYのRS新高値と株価に先行した銘柄、21日EMAの上抜け・下抜け、EMA21の上にある銘柄数。なければ「なし」と1行）、
市場全体とテック内部（daily.md 6b節：テック内部のラベルと高値から−20%以上の比率、ブレイクの伸び、市場Tapeレジームと指数の崩れガード、先導セクター上位3と半導体・テックの先導株数（4週前比）、ヘッジ条件、長く持つ分の目安。変化があれば先頭に）、
川下（daily.md 4c節：5銘柄の前日比と対SOXX、「先に崩れているか」の1文）、
重要ニュース、今日・明日のイベント（政策の固定日程が7営業日以内にあればその行も）、週次判定との整合（反転リスク「米国内のDC規制・許認可」「AI投資の資金調達・信用」に触れる材料があった日はその1行も）、データ監査。
reports/daily/<us_as_of>.md を SendUserFile で送る。

## 5. 欠けた日の補完（v1.4。利用上限などで日次が配信できなかった日を後日作る）
- 判定の履歴（history_levels.csv、history_key.csv）は GitHub Actions が毎朝作るので欠けない。欠けるのはレポートと、その日の daily_signals.json（上書きされる）。
  build_snapshot.py と build_signals.py の `--as-of YYYY-MM-DD` で、その日までの足だけから levels・daily_signals を作り直せる（11/5 で検証済み：history_levels.csv の同じ日の段階と完全一致）。
- 作り方（1日分 D ごと）：
  1. `rm -rf /home/claude/sbf_D && mkdir /home/claude/sbf_D && cp /home/claude/sd-data/* /home/claude/sbf_D/`
  2. `cd /home/claude/semis-data && python3 build_snapshot.py --out /home/claude/sbf_D --as-of D && python3 build_health.py --out /home/claude/sbf_D --as-of D && python3 build_signals.py --out /home/claude/sbf_D --as-of D`
     （数秒。daily_signals.json に backfill が入る。［v1.5］sector_health.json も D 時点の値になる（build_signals より前に実行する）。macro は実行時点の最新値のまま。data ブランチには書かない）
  3. daily.md の形式で補完版を書く：入力は /home/claude/sbf_D/daily_signals.json・semis_manifest.json・semis_snapshot.csv・sector_health.json。タイトルに「（補完版）」、冒頭に
     「この日の日次は配信できなかったため、後日 D までのデータで作り直したもの。シグナル・段階・水準・RS線はエンジンの再計算で当時と同じ。ニュース（7節）と Web確認は含まない。
     6b節は米国株側の history_signals.csv の D の行（regime_effective、IX3_guard、BR5_tech・ラベル、FB1_stalling、top_sectors、tech_leaders、semi_leaders、hedge_status、spy_model）から転記」と書く。
     Web確認はしない。7節は「補完のため省略」。9節（週次判定との整合）は当時の直近の週次に対して書く。
  4. 保存：reports/daily/D.md（commit「daily D (backfill)」）。handoff/daily_state.yaml の last_us_as_of は、補完した日より新しい日次があるなら変えない（notes に補完した旨を1行）。
  5. 配信：SendUserMessage で冒頭ブロックと本日のシグナル（high だけ）を短く（「補完版」と明記）。SendUserFile で本文。
- 補完は今日の日次より先に、古い日から順に。1日分に5分超かかるときは今日の日次を先に出し、補完は件数だけ知らせる。
- 週次が欠けたとき（土曜の定期実行が動かなかった）はここでは作らない。ユーザーの依頼で schedule_weekly.md の第7節（補完）に従う。

