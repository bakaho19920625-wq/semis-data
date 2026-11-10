# 半導体・メモリー定点観測｜日次の定期実行（流れ） schedule_daily v2.0
# 定期実行（スケジュールタスク）の入口。上から順に進める。定期実行の本文は、このファイルを読む指示だけ。手順を変えるときはこのファイルを直す。
# レポートの書き方は prompts/daily.md と prompts/daily/（節ごと）。欠けた日の補完は prompts/daily_backfill.md。読む用の保管ページへの保存は prompts/archive_page.md。変更の履歴は prompts/CHANGELOG.md（本文には履歴を書かない）。

## 0. 設定
- 深さ（effort）：xhigh
  第6節で書き手（Agent）に渡す深さ。変えるときはこの1行だけ直す（low／medium／high／xhigh／max）。
- 動く時刻（日本時間）：火〜土 07:21 が1回目。09:21・12:21 は再試行（データ未更新や利用上限で前の回が動けなかった日のため）。
- 米国株側の日次（7:07）の後に動く。レポートの6b節で米国株側の signals.json を転記するため。
- この実行は、会話の記憶がない新しいセッションで動く。

## 1. 準備
- /home/claude/semis-data がなければ `git clone --depth 1 https://github.com/bakaho19920625-wq/semis-data /home/claude/semis-data`
  （公開リポジトリなので事前の準備は要らない）。
  あれば `git -C /home/claude/semis-data pull -q`。
- data ブランチ：`rm -rf /home/claude/sd-data && git clone -q --depth 1 --branch data https://github.com/bakaho19920625-wq/semis-data.git /home/claude/sd-data`

## 2. データの新しさ
/home/claude/sd-data の `semis_manifest.json`（基準日 us_as_of）と `prices_manifest.json` を読み、次の順に確かめる。
1. 新しさの確認：`us_as_of` が直近の米国取引日（日本時間の今日の前日にあたるET日付。土日・NYSE休場日を除く）か確認する。
   - 前日が休場なら「新しい取引日はありません（休場）」と1行送って終了。
   - 生成時刻の確認：`prices_manifest.json` の `generated_utc` が「`us_as_of` の日付の 21:20 UTC」より前なら、そのデータは米国の取引時間中（引け前）に作られたもので、基準日が合っていても終値ではない（2026-11-09 に、取引時間中の手動実行で実際に起きた）。
     日付が古いときと同じ扱いにして、下の手順でデータ更新を起動する。
     夏時間の引けは 20:20 UTC だが、判定は一年じゅう 21:20 UTC でよい（夏の 20:20〜21:20 UTC に作られたデータを取り直すだけで害はない）。
     取り直しても生成時刻が引けより前のままなら「GitHubデータ未更新」と同じ扱いにする。
   - 取引日なのに古ければ、まず朝の自動実行が起動していない可能性があるので、シェルが使える環境では自分でデータ更新を起動する（git の push で起動する）。
     /home/claude/semis-data（main のクローン）で `mkdir -p refresh && date -u +%Y-%m-%dT%H:%M:%SZ > refresh/request.txt && git add refresh/request.txt && git commit -q -m "refresh request" && git push origin main`（この push で .github/workflows/update.yml が動く。push が断られたら第8節の「push が断られたとき」に従い、それでも駄目なときだけ従来の `gh api -X POST repos/bakaho19920625-wq/semis-data/actions/workflows/update.yml/dispatches -f ref=main` を1回試す。エラーなら起動できなかったものとして扱う）。
     完了は git で確かめる：30秒おきに `git -C /home/claude/semis-data fetch -q origin data && git -C /home/claude/semis-data show FETCH_HEAD:semis_manifest.json` の generated_utc を見て、push した時刻より新しくなるまで最大10分待ち、data ブランチを取り直す（ワークフローは前営業日の足が入るまで10分おきに最大6回取り直すので、10分で終わらないことがある。その場合は次へ）。
     それでも古い、または起動できない環境なら「GitHubデータ未更新（基準日○○、生成○○）」として終了（送るかどうかは下の「送る・送らない」）。
     起動した場合は、第6節で書き手に伝える（レポートの10節に書かせる）。
- 送る・送らない：
  - 「休場」なら、7:21 の1回目だけその1行を SendUserMessage で送って終了（9:21・12:21 の再試行では何も送らずに終了）。
    「GitHubデータ未更新」なら、7:21 の1回目は何も送らず終了（9:21 の再試行に任せる）、9:21・12:21 の再試行ならその1行を送って終了（12:21 は 9:21 が利用上限で動けなかった日のため。重複して届くことがあるが、沈黙より良い）。
    いずれも保存しない。

## 3. 配信済みの確認
- 同じ us_as_of の日次をすでに配信済み（handoff/daily_state.yaml の last_us_as_of が今回の us_as_of と同じ、または reports/daily/<us_as_of>.md がある）なら、何も送らず終了（9:21・12:21 の再試行で前の回が成功していたとき）。
  この回は SendUserMessage を使わない（通知を出さない）。
  prompts/archive_page.md の手順 1〜3（種類 semis_daily）だけを行い（ページに入っていない日次があれば入れる）、
  最後の返答を次の1行だけにする：「<us_as_of> の日次レポートは配信済みです。レポートはここに並んでいます：https://claude.ai/artifact/RsGNScaBqUn628DmNiUcvX」
  配信済みなら、ここで終わる。第4節から先と prompts/daily.md は読まなくてよい。

## 4. 米国株側のデータ
- 米国株指標チェックの判定結果（市場全体・テック内部・ブレイクの伸び・先導セクター・ヘッジ条件・長期の目安。レポートの6b節で転記する）：
  `curl -sSf https://raw.githubusercontent.com/bakaho19920625-wq/market-data/data/signals.json -o /home/claude/mkt_signals.json`
  届かなければ `rm -rf /home/claude/mkt-data && git clone -q --depth 1 --branch data https://github.com/bakaho19920625-wq/market-data.git /home/claude/mkt-data`
  （signals.json はその中）。
  取れなければ 6b節は「取得できず」。
  market-data 側は起動しない（更新が実行中なら下のとおり最大5分待つ）。
- 基準日の確認：market-data の signals.json：`as_of_market_date` が `us_as_of` と同じか確認する。
  違うときは、market-data 側のデータ更新が動いている途中のことがあるので、30秒おきに `git ls-remote https://github.com/bakaho19920625-wq/market-data.git refs/heads/data` の値を見て、変わったら `git clone -q --depth 1 --branch data` で取り直す（最大5分。gh は使わない。raw の URL は数分古い値を返すことがあるので取り直しには使わない。起動はしない。米国株側の日次 7:07 が起動しているはず）。
  それでも違う、または取得できないときは、そのまま第6節へ進み、書き手に伝える（6b節での書き方は prompts/daily/s06b_market.md にある）。
- 買い戻しの燃料：`curl -sSf https://raw.githubusercontent.com/bakaho19920625-wq/market-data/main/reports/flows/fuel_latest.yaml -o /home/claude/mkt_fuel.yaml`（届かなければ、無いまま進む）。

## 5. 欠けた日と、先週の週次の確認
- 欠けた日の確認：reports/daily/ に無い米国取引日（/home/claude/sd-data/history_levels.csv の us_as_of の列が取引日の一覧）が直近にあれば、今日の日次の前に prompts/daily_backfill.md を読んで補完版を作る（最大3日分。古い順）。
- 直近の金曜の週次 reports/<金曜の日付>.md が無いとき、火・水・木の配信（基準日が月〜水の日次）では、配信の冒頭に「先週の週次定点観測は未作成です。「半導体の週次を補完して」で作れます」と1行出す（日次の中で週次は作らない）。

## 6. 作成（書き手に任せる）
- レポートを書く作業は、Agent 1つに任せる（subagent_type: "general-purpose"、effort: 第0節の深さ、run_in_background: false）。
  深さを指定できるのは Agent だけなので、ここでは自分で書かない。
  ほかの作業（準備・点検・保存・配信）は下請けに出さない（出しても速くならず、費用が増えるだけのため）。
- 渡す文（そのまま使い、〔 〕だけ埋める）：
  「半導体・メモリー定点観測の日次レポート（基準日 〔us_as_of〕）を書いてください。
  /home/claude/semis-data/prompts/daily.md を読み、その進め方どおりに進めてください（各節は prompts/daily/ の節ごとのファイルを、その節を書く直前に読みます）。
  入力は /home/claude/sd-data/（data ブランチ）、/home/claude/semis-data/handoff/latest.yaml と handoff/daily_state.yaml、/home/claude/mkt_signals.json、/home/claude/mkt_fuel.yaml です。
  出力は /home/claude/semis-data/reports/daily/〔us_as_of〕.md と、handoff/daily_state.yaml の更新です。git の操作と配信は、こちらで行うのでしないでください。
  伝えておくこと：〔第2節・第4節で分かったこと。例：データ更新を起動した（10節に書く）／run_status の signals が failure／market-data の基準日が違う（○○）／mkt_signals.json・mkt_fuel.yaml が取得できなかった／なし〕
  書き終えたら daily.md の「書き終えたら」のとおり点検し、最後に、レポートのパス・点検の結果・Web確認の回数・週次判定の見直し候補（あれば）を返してください。」
- Agent が道具の一覧に無い環境では、自分で prompts/daily.md に従って書く（このときは深さを指定できない）。

## 7. 点検
- 自分でも点検プログラムを実行する（書き手の報告だけで済ませない。数秒で終わる）：
  `python3 /home/claude/semis-data/tools/check_report.py semis_daily /home/claude/semis-data/reports/daily/<us_as_of>.md --data /home/claude/sd-data --mkt /home/claude/mkt_signals.json`
- 「不合格」の行があれば、同じ書き手に戻して直させる（SendMessage。最大2回）。
  戻すときは、不合格の行をそのまま貼り、「次の項目がまだ残っています。直してから、もう一度点検の結果を返してください」と、残っている項目を名指しする。
  SendMessage が使えないとき、または書き手が応えないときは、不合格の節だけ自分で直す（その節のファイルを読んでから）。
- 2回直しても残った不合格は、配信の5（データ監査で伝えるべきこと）に「点検で残った項目：○○」と1行で書く。配信は止めない。
- 点検プログラムそのものが動かない・途中で止まるときは、点検を飛ばして先へ進み、配信の同じ場所に「点検プログラムが動かなかった」と1行で書く。
- 「注意」の行は不合格ではない。読んで、直す必要があるものだけ直させる。

## 8. 保存
- 書き手が書いた reports/daily/<us_as_of>.md と handoff/daily_state.yaml（last_us_as_of、reported_urls、review_candidates）を確かめる。
- `git add -A` → commit「daily <us_as_of>」→ `git push origin main`。
  data ブランチには書かない。
- push が断られたとき（データ更新の起動の push も同じ）：
  ・「fetch first」「non-fast-forward」と出た（ほかの更新が先に入っただけで、権限の問題ではない）→ `git pull -q --rebase origin main` のあと、もう一度 push する。
  ・それ以外（403 など、書き込みが許可されていない）→ このときだけ ToolSearch（query: "add_repo"）で名前が add_repo で終わるツールを探し、見つかれば
    add_repo（owner: "bakaho19920625-wq", repo: "semis-data", access: "push"）を呼んでから、同じ push をもう1回だけ試す。
    それでも断られたら、エラー文をそのまま控え、配信の最後に「GitHub に保存できませんでした：（エラー文）」と1行で書く（推測で原因を書かない）。
    レポートの配信は続ける。
  ・push が実際に断られたとき以外は、add_repo・gh・書き込みの道具の状態を、レポートにも配信にも書かない（何も送らず終了する回でも同じ）。
- 読む用の保管ページ「半導体・メモリー 日次レポート」への保存：GitHub への push のあとに、prompts/archive_page.md の手順を種類 semis_daily で行う。

## 9. 配信
SendUserMessage は**1画面**（日本語でおよそ600〜900字。重要な変化が多い日でも1,200字まで）。
全文は添付の本文で読めるので、配信には判断に要るものだけを書く：
1. 冒頭ブロック（レポートの「今日のひとこと」3行＋「なぜその判断か」をそのまま）
2. 前日から変わった点（レポートの同じ名前の節をそのまま。なければ「前日から状態の変化なし」）
3. 1行ずつ：底の局面（レポートの0節。局面が none 以外の日だけ。起点比と、二番底の線・底割れの線。売買の合図ではない言い方で）／戻りの質（2b節の最後の1行。調整局面の日だけ）／買い戻しの燃料（6b節の1行）
4. 今日・明日のイベント（当日と翌日のものだけ。政策の固定日程は7営業日以内なら1行）
5. 週次判定の見直し候補（ある日だけ。反転リスク「米国内のDC規制・許認可」「AI投資の資金調達・信用」に触れる材料があった日はその1行も）と、データ監査で伝えるべきこと（データ未更新・取得失敗・補完・週次未作成。なければ書かない）
シグナルの全件、市場表、メモリー株、意識される水準、RS線、川下、市場全体とテック内部の詳細、ニュースの本文は配信に書かない（本文にある）。
最後に「全文は添付のファイルと、保管ページ（これまでの日次が並ぶ）：https://claude.ai/artifact/RsGNScaBqUn628DmNiUcvX」と1行（このリンクは毎回出す）。
reports/daily/<us_as_of>.md を SendUserFile で送る。
送る前に、配信の文を /home/claude/delivery.txt に書き、`python3 /home/claude/semis-data/tools/check_report.py delivery /home/claude/delivery.txt --max 1200 --link https://claude.ai/artifact/RsGNScaBqUn628DmNiUcvX` で長さと最後の行を確かめる。

## 10. この実行での注意（無人で動くため）
- この実行には、途中で答える人がいない。道具を呼ばずに文だけを返すと、そこで実行が終わり、続きは誰も頼まない。
  第8節の保存と第9節の配信が終わるまで、次の作業の道具を呼び続ける。
- 次の4つの止まり方をしない：(1)「次は○○をします」と書いただけで終える、(2)「続けますか」と尋ねて待つ、
  (3) 決めなくても進められることを並べて判断を求める、(4) 区切り（書き手が書き終えた、点検が通った、push できた）で終える。
  途中経過を書くときは、次の道具の呼び出しと同じ返答の中に書く。
- 止まってよいのは、この手順書が「終了」と書いている場面だけ：休場とGitHubデータ未更新（第2節）、配信済み（第3節）、そして第8節の保存と第9節の配信がすべて終わったとき。
- 最初に、第1節〜第9節をやることリストに入れ（TaskCreate が使えるとき）、1つ終えるごとに消す。
- 障害（エラー、タイムアウト、空の結果、取得の失敗）は、原因を見て別の方法を試す。代わりの手順が決まっているものは、その節に書いてあるとおりにする。
- 変えないもの（障害ではなく決まり）：data ブランチ、prompts/ とプログラム、market-data リポジトリ。個人の保有・数量・売買指示は扱わない。
- GitHub への書き込みは git の push だけで行う（第2節のデータ更新の起動と、第8節の保存）。
  add_repo と gh は、第8節の「push が断られたとき」以外では使わない。
  `gh auth status` も実行しない（gh が使えるときでも「The token in GH_TOKEN is invalid.」と出るので、判断材料にならない。2026-11-10 に確認）。
