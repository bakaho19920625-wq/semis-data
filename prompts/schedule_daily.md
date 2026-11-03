# 半導体・メモリー定点観測｜日次の定期実行 手順（schedule_daily v1.2）
# 定期実行（スケジュールタスク。火〜土 07:21 JST の1回目と、データ未更新のときの 09:21 の再試行。会話の記憶がない新しいセッションで動く）の本文は、このファイルを読む指示だけ。手順を変えるときはこのファイルを直す。
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
- 入力：/home/claude/sd-data/daily_signals.json、run_status.json、semis_manifest.json、semis_snapshot.csv、
  /home/claude/semis-data/handoff/latest.yaml、handoff/daily_state.yaml、/home/claude/mkt_signals.json。Web確認は最大6回。
- ［v1.2］同じ us_as_of の日次をすでに配信済み（handoff/daily_state.yaml の last_us_as_of が今回の us_as_of と同じ）なら、何も送らず終了（9:21 の再試行で 7:21 が成功していたとき）。
- daily.md 手順1 の新しさの判定で「休場」なら、7:21 の1回目だけその1行を SendUserMessage で送って終了（9:21 では送らない）。
  「GitHubデータ未更新」なら、7:21 の1回目は何も送らず終了（9:21 の再試行に任せる）、9:21 の再試行ならその1行を送って終了。いずれも保存しない。

## 3. 保存
- レポートを /home/claude/semis-data/reports/daily/<us_as_of>.md に書き、handoff/daily_state.yaml を更新（last_us_as_of、reported_urls、review_candidates）。
- `git add -A` → commit「daily <us_as_of>」→ `git push origin main`。data ブランチには書かない。

## 4. 配信
SendUserMessage で2〜3画面：冒頭ブロック（daily.md の「今日のひとこと」3行＋「なぜその判断か」をそのまま）、本日のシグナル（high→medium、全件）、解釈（daily.md 2節）、
意識される水準（SOXX・SOXL・DRAM・MU・SNDK・SKHY の終値と SMA50/200、直近20日高安）、
RS線（daily.md 6節：対SPYのRS新高値と株価に先行した銘柄、21日EMAの上抜け・下抜け、EMA21の上にある銘柄数。なければ「なし」と1行）、
市場全体とテック内部（daily.md 6b節：テック内部のラベルと高値から−20%以上の比率、ブレイクの伸び、市場Tapeレジームと指数の崩れガード、先導セクター上位3と半導体・テックの先導株数（4週前比）、ヘッジ条件、長く持つ分の目安。変化があれば先頭に）、
重要ニュース、今日・明日のイベント、週次判定との整合、データ監査。
reports/daily/<us_as_of>.md を SendUserFile で送る。
