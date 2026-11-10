# 半導体・メモリー定点観測｜週次の定期実行 手順（流れ） schedule_weekly v2.0
# 定期実行（スケジュールタスク）の本文は、このファイルを読む指示だけ。手順を変えるときはこのファイルを直す。
# 収集は prompts/collector.md、判定は prompts/judge.md と prompts/judge/（判定基準と節ごと）が正本。ここは「準備・2段階の回し方・点検・保存・配信」の段取りだけ。
# 欠けた週の補完は prompts/weekly_backfill.md。読む用の保管ページへの保存は prompts/archive_page.md。変更の履歴は prompts/CHANGELOG.md。

## 0. 設定
- 深さ（effort）：xhigh
  第3節の収集と第4節の判定で Agent に渡す深さ。変えるときはこの1行だけ直す（low／medium／high／xhigh／max）。
- 動く時刻（日本時間）：土曜 10:11 が1回目。14:11・19:11 は再試行（利用上限などで前の回が動けなかった日のため）。
- この実行は、会話の記憶がない新しいセッションで動く。

## 1. 準備
- /home/claude/semis-data がなければ `git clone --depth 1 https://github.com/bakaho19920625-wq/semis-data /home/claude/semis-data`
  （公開リポジトリなので事前の準備は要らない）。
  あれば `git -C /home/claude/semis-data pull -q`。
- data ブランチ：`rm -rf /home/claude/sd-data && git clone -q --depth 1 --branch data https://github.com/bakaho19920625-wq/semis-data.git /home/claude/sd-data`
- 米国株指標チェックの判定結果（週次の4c節・MARKET_CONTEXT・反転リスク「テック内部の崩れ」に転記するだけで、採点には使わない）：
  `curl -sSf https://raw.githubusercontent.com/bakaho19920625-wq/market-data/data/signals.json -o /home/claude/mkt_signals.json`
  届かなければ `rm -rf /home/claude/mkt-data && git clone -q --depth 1 --branch data https://github.com/bakaho19920625-wq/market-data.git /home/claude/mkt-data`。
- semis_manifest.json の us_as_of を日付ラベル YYYY-MM-DD にする。
  直近の米国取引日より古ければ「GitHubデータ未更新」と明記して続行。

## 2. 配信済みの確認
- 同じ日付の週次がすでにある（reports/<日付>.md があり、handoff/latest.yaml の REPORT_DATE が同じ）なら、何も送らず終了する（再試行の回が、前の回が成功した日に二重に作らないため。再試行の時刻が増えても同じ規則）。
  この回は SendUserMessage を使わない（通知を出さない）。
  prompts/archive_page.md の手順 1〜3（種類 semis_weekly）だけを行い（ページに入っていない週次があれば入れる）、
  最後の返答を次の1行だけにする：「<日付> の週次定点観測は配信済みです。レポートはここに並んでいます：https://claude.ai/artifact/8yev96zRruPECPTdCEu7P8」
  配信済みなら、ここで終わる。第3節から先と prompts/collector.md・prompts/judge.md は読まなくてよい。

## 3. 収集（第1段階）
- Agent（subagent_type: "general-purpose"、effort: 第0節の深さ、run_in_background: false）に prompts/collector.md に完全に従わせる。
  参照は docs/sources.md、/home/claude/sd-data/semis_manifest.json、/home/claude/sd-data/fundamentals_latest.json（機械取得の実績値と SEC 確認用URL。collector.md 第2節）、handoff/latest.yaml、前回の evidence/latest.yaml（突き合わせ用。上書きする前に読ませる）。
- run_status.json の fundamentals が failure、または fundamentals_latest.json の status が failed なら、その旨を収集エージェントに伝え（値は前回のまま）、実績値は従来どおりWebで探させる。
- 出力は evidence/<日付>.yaml と evidence/latest.yaml（yaml.safe_load で読めることを確認。EVIDENCE_VERSION: v7.3、MACHINE_FUNDAMENTALS・RECONCILED・DC_TIMING がある（DC_TIMING の中に market_credit と construction_actuals の欄がある。値が取れなかった週は空でよい）。DC_TIMING.regulation.texas_pause.state と projects が埋まっているか見る。空なら収集エージェントに P1-7 の a・b を確認させる（1回まで））。
- 収集が終わったら、証拠YAMLを機械で点検する：`python3 /home/claude/semis-data/tools/check_report.py semis_evidence /home/claude/semis-data/evidence/latest.yaml`
  「不合格」（collector.md のひな形にある項目が無い、YAML として読めない）があれば、その行をそのまま収集エージェントに戻して直させる（SendMessage。1回まで）。
- flags に adr_ratio_or_data_suspect があっても SKHY の ADS 比率は確認済み（0.1株、424B4）なので、終値の確認だけでよい。
- 月の最初の実行なら DRAM ETF の公式情報も確認。

## 4. 判定（第2段階）
- 別の Agent（subagent_type: "general-purpose"、effort: 第0節の深さ、run_in_background: false）に prompts/judge.md に完全に従わせる。
- 入力：handoff/latest.yaml、handoff/forecasts.csv、/home/claude/sd-data/ の各ファイル（sector_health.json・history_health.csv を含む）、evidence/latest.yaml、/home/claude/mkt_signals.json。
- 出力：reports/<日付>.md、handoff/latest.yaml と handoff/<日付>.yaml、forecasts.csv の追記・判定更新。
- 期限が来た予測（forecasts.csv の open で deadline 経過）を必ず判定させる。

## 5. 点検（自分で）
- 自分でも点検プログラムを実行する（書き手の報告だけで済ませない。数秒で終わる）：
  `python3 /home/claude/semis-data/tools/check_report.py semis_weekly /home/claude/semis-data/reports/<日付>.md --data /home/claude/sd-data --mkt /home/claude/mkt_signals.json`
- 「不合格」の行があれば、同じ書き手に戻して直させる（SendMessage。最大2回）。
  戻すときは、不合格の行をそのまま貼り、「次の項目がまだ残っています。直してから、もう一度点検の結果を返してください」と、残っている項目を名指しする。
  SendMessage が使えないとき、または書き手が応えないときは、不合格の節だけ自分で直す（その節のファイルを読んでから）。
- 2回直しても残った不合格は、配信の4（データ監査で伝えるべきこと）に「点検で残った項目：○○」と1行で書く。配信は止めない。
- 点検プログラムそのものが動かない・途中で止まるときは、点検を飛ばして先へ進み、配信の同じ場所に「点検プログラムが動かなかった」と1行で書く。
- 「注意」の行は不合格ではない。読んで、直す必要があるものだけ直させる。
- 点検プログラムが見ないものも含め、次を自分で確かめる（不一致は判定エージェントに差し戻す。プログラムの不合格と合わせて最大2回）：
  - handoff/latest.yaml が読める。
    LEVELS.S/D が /home/claude/sd-data/levels.json と一致。
    SCENARIOS 各期間の合計が100。
  - FORECASTS.new が forecasts.csv にある。
  - MARKET_CONTEXT が /home/claude/mkt_signals.json の値と一致し（先導セクター・ヘッジ・長期モデルの項目を含む）、反転リスク「テック内部の崩れ」の状態が prompts/judge/criteria.md 5節の規則どおり。
  - 報道値（reported_unverified）と XBRL 未反映の値（pending_xbrl）に本文で「要確認」が付き、UNCONFIRMED_ITEMS に残っている。
    RECONCILED の mismatch が0節に書かれている。
  - 冒頭ブロック（今日のひとこと3行＝半導体／メモリー／行動の目安、＋なぜその判断か）がある。
    本文の状態語が言葉→数字（記号）の形になっている。
  - LEVELS.A の A4・A5 が数値（−2〜+2）になっている（除外なら0節に「DC_TIMING なし」の理由がある）。
    6a節に5つの見出しと scenario_lean がある。
    YAML に DC_TIMING と DOWNSTREAM_RS があり、反転リスク「米国内のDC規制・許認可」「AI投資の資金調達・信用」の状態が本文10節に書かれている。
    12節に政策の固定日程の表がある。
  - 4d節とYAMLの SECTOR_HEALTH が /home/claude/sd-data/sector_health.json の値と一致している（label、risk.count、washout.count、washout.phase の code・anchor_date・close_vs_anchor_pct、strip の緑の数と state。再計算していない）。
    そろい数が3未満で局面が none 以外のとき「まだ売られ尽くしていない」と書いていない。
    「過去5回で外れなし」「だまし0%」と書いていない。
    帯・危険の目安・底の目安が採点（LEVELS）・VIEW・行動の目安の「買え」「売れ」に使われていない。
    底の目安が3つそろった最初の週（初回は 2026-11-05 の分）は FORECASTS.new に26週の予測がある。
    sector_health.json が無い・古いときは4d節が「未取得」になっている。
  - 冒頭ブロックの「半導体」「メモリー」の行が、株価の状態と市況の見方を分けて書いている（prompts/judge/a_opening.md。「やや強気」などのラベルだけで行を始めていない。値動きの点数が30未満、または反転リスクの発動が2つ以上の週は、株価の状態が先）。
  - 10a節（需給と信用の市場の値）があり、YAML に FLOWS_CREDIT がある。
    ①買い戻しの燃料は market-data の reports/flows/fuel_latest.yaml の値と一致（再計算していない。読めない週は「未取得」）、②の HY・CCC は /home/claude/sd-data/semis_manifest.json の macro.latest の値。
    10a節の値が採点（LEVELS）・反転リスクの段階・シナリオ確率に使われていない。
  - 倍率に基準（20日平均・50日平均）が書かれ、4d節で簡易版の割合を「上昇中」「下落中」と書いていない。

## 6. 保存
- `git add -A` → commit「report <日付>」→ `git push origin main`。
  data ブランチには書かない。
- push が断られたとき：
  ・「fetch first」「non-fast-forward」と出た（ほかの更新が先に入っただけで、権限の問題ではない）→ `git pull -q --rebase origin main` のあと、もう一度 push する。
  ・それ以外（403 など、書き込みが許可されていない）→ このときだけ ToolSearch（query: "add_repo"）で名前が add_repo で終わるツールを探し、見つかれば
    add_repo（owner: "bakaho19920625-wq", repo: "semis-data", access: "push"）を呼んでから、同じ push をもう1回だけ試す。
    それでも断られたら、エラー文をそのまま控え、配信の最後に「GitHub に保存できませんでした：（エラー文）」と1行で書く（推測で原因を書かない）。
    レポートの配信は続ける。
  ・push が実際に断られたとき以外は、add_repo・gh・書き込みの道具の状態を、レポートにも配信にも書かない（何も送らず終了する回でも同じ）。
- 読む用の保管ページ「半導体・メモリー 週次定点観測」への保存：GitHub への push のあとに、prompts/archive_page.md の手順を種類 semis_weekly で行う。

## 7. 配信
SendUserMessage は**1画面**（日本語でおよそ800〜1,200字）。
全文は添付の本文で読めるので、配信には判断に要るものだけを書く：
1. 冒頭ブロック（レポートの「今日のひとこと」3行＋「なぜその判断か」をそのまま）
2. 前回から変わった点：総合点（帯）と前回比、段階が変わった小項目（drivers）の上位3、反転リスクで状態が変わったものと発動中のもの（「テック内部の崩れ」「米国内のDC規制・許認可」「AI投資の資金調達・信用」は状態を必ず1語で）、予測の判定結果と累積の的中率
3. 1行ずつ：セクターの状態（4d節：公式ステージの分布と判定、危険の目安 n/3、底の目安 n/3 と底の局面。売買の合図ではない言い方で）／需給と信用（10a節：燃料の棒と残り約○割、信用の1行、まとめ）／AIインフラの稼働タイミング（6a節の scenario_lean。状態が変わった週は規制の状態と後ろ倒しの件数も）
4. 次回の監視項目3つと、データ監査で伝えるべきこと（未更新・取得失敗・要確認の多い項目。なければ書かない）
6カテゴリの内訳、S/D の小項目、市場全体とテック内部（4c節）の詳細、シナリオ確率の表は配信に書かない（本文にある。前回から変わった週だけ2の中で1行）。
最後に「全文は添付のファイルと、保管ページ（これまでの週次が並ぶ）：https://claude.ai/artifact/8yev96zRruPECPTdCEu7P8」と1行（このリンクは毎回出す）。
reports/<日付>.md を SendUserFile で送る。
送る前に、配信の文を /home/claude/delivery.txt に書き、`python3 /home/claude/semis-data/tools/check_report.py delivery /home/claude/delivery.txt --max 1200 --link https://claude.ai/artifact/8yev96zRruPECPTdCEu7P8` で長さと最後の行を確かめる。

## 8. この実行での注意（無人で動くため）
- この実行には、途中で答える人がいない。道具を呼ばずに文だけを返すと、そこで実行が終わり、続きは誰も頼まない。
  第6節の保存と第7節の配信が終わるまで、次の作業の道具を呼び続ける。
- 次の4つの止まり方をしない：(1)「次は○○をします」と書いただけで終える、(2)「続けますか」と尋ねて待つ、
  (3) 決めなくても進められることを並べて判断を求める、(4) 区切り（書き手が書き終えた、点検が通った、push できた）で終える。
  途中経過を書くときは、次の道具の呼び出しと同じ返答の中に書く。
- 止まってよいのは、この手順書が「終了」と書いている場面だけ：配信済み（第2節）、そして第6節の保存と第7節の配信がすべて終わったとき。
- 最初に、第1節〜第7節をやることリストに入れ（TaskCreate が使えるとき）、1つ終えるごとに消す。
- 障害（エラー、タイムアウト、空の結果、取得の失敗）は、原因を見て別の方法を試す。代わりの手順が決まっているものは、その節に書いてあるとおりにする。
- 収集と判定の Agent は順番に1つずつ動かす（収集の出力を判定が読むため）。Agent が戻ったら、同じ返答の中で次の節の道具を呼ぶ。
- 変えないもの（障害ではなく決まり）：data ブランチ、prompts/ とプログラム、market-data リポジトリ。個人の保有・数量・売買指示は扱わない。
- GitHub への書き込みは git の push だけで行う（第6節の保存）。
  add_repo と gh は、第6節の「push が断られたとき」以外では使わない。
  `gh auth status` も実行しない（gh が使えるときでも「The token in GH_TOKEN is invalid.」と出るので、判断材料にならない。2026-11-10 に確認）。
