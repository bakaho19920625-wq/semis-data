# 半導体・メモリー定点観測｜週次の定期実行 手順（schedule_weekly v1.9。v1.9＝読む用の保管ページ「半導体・メモリー 週次定点観測」への保存（第5節。週次だけが基準日順に並ぶページ）、配信の最後と「すでにあるので終了する回」の最後にそのページのリンク（第1節、第6節、第7節）。v1.8＝収集 v7.3・判定 v6.9 対応：点検に10a節（需給と信用の市場の値）と冒頭ブロックの形（市況／株価）を追加、配信を1画面に。v1.7＝GitHub への書き込みを git の push に一本化（add_repo と gh の確認を外す。add_repo は push が断られたときだけ）。v1.6＝点検・配信に底の局面（judge v6.8）。v1.3＝証拠 v7.2（DC_TIMING）・判定 v6.6（A4・A5、反転リスク2項目、6a節）対応。v1.4＝14:11 の再試行の重複防止、欠けた週の補完（第7節）。v1.5＝判定 v6.7 対応：点検・配信・補完に sector_health.json（セクターの状態、4d節・SECTOR_HEALTH）を追加）
# 定期実行（スケジュールタスク。土曜 10:11 JST、利用上限などで動けなかったときの再試行 14:11・19:11。19:11 は 2026-11-10 に追加：11/7 は 10:11 が利用上限で失敗した。4時間後では上限が戻らないことがあるため、夕方にもう1回置く。会話の記憶がない新しいセッションで動く）の本文は、このファイルを読む指示だけ。手順を変えるときはこのファイルを直す。
# 収集は prompts/collector.md、判定は prompts/judge.md が正本。ここは「準備・2段階の回し方・点検・保存・配信」の段取りだけ。

## 1. 準備
- /home/claude/semis-data がなければ `git clone --depth 1 https://github.com/bakaho19920625-wq/semis-data /home/claude/semis-data`
  （公開リポジトリなので事前の準備は要らない）。あれば `git -C /home/claude/semis-data pull -q`。
- ［v1.7］GitHub への書き込みは git の push だけで行う（第5節の保存）。add_repo と gh は、第5節の「push が断られたとき」以外では使わない。
  `gh auth status` も実行しない（gh が使えるときでも「The token in GH_TOKEN is invalid.」と出るので、判断材料にならない。2026-11-10 に確認）。
- data ブランチ：`rm -rf /home/claude/sd-data && git clone -q --depth 1 --branch data https://github.com/bakaho19920625-wq/semis-data.git /home/claude/sd-data`
- 米国株指標チェックの判定結果（judge.md 4c節・MARKET_CONTEXT・反転リスク「テック内部の崩れ」に転記するだけで、採点には使わない）：
  `curl -sSf https://raw.githubusercontent.com/bakaho19920625-wq/market-data/data/signals.json -o /home/claude/mkt_signals.json`
  届かなければ `rm -rf /home/claude/mkt-data && git clone -q --depth 1 --branch data https://github.com/bakaho19920625-wq/market-data.git /home/claude/mkt-data`。
- semis_manifest.json の us_as_of を日付ラベル YYYY-MM-DD にする。直近の米国取引日より古ければ「GitHubデータ未更新」と明記して続行。
- ［v1.4］同じ日付の週次がすでにある（reports/<日付>.md があり、handoff/latest.yaml の REPORT_DATE が同じ）なら、何も送らず終了する（再試行の回が、前の回が成功した日に二重に作らないため。再試行の時刻が増えても同じ規則）。
  ［v1.9］この回は SendUserMessage を使わない（通知を出さない）。第5節の「読む用の保管ページ」の手順 1〜3 だけを行い（ページに入っていない週次があれば入れる）、
  最後の返答を次の1行だけにする：「<日付> の週次定点観測は配信済みです。レポートはここに並んでいます：https://claude.ai/artifact/8yev96zRruPECPTdCEu7P8」

## 2. 収集（第1段階）
Agent（general-purpose）に prompts/collector.md に完全に従わせる。参照は docs/sources.md、/home/claude/sd-data/semis_manifest.json、
/home/claude/sd-data/fundamentals_latest.json（機械取得の実績値と SEC 確認用URL。collector.md 第2節）、handoff/latest.yaml、前回の evidence/latest.yaml（突き合わせ用。上書きする前に読ませる）。
run_status.json の fundamentals が failure、または fundamentals_latest.json の status が failed なら、その旨を収集エージェントに伝え（値は前回のまま）、実績値は従来どおりWebで探させる。
出力は evidence/<日付>.yaml と evidence/latest.yaml（yaml.safe_load で読めることを確認。EVIDENCE_VERSION: v7.3、MACHINE_FUNDAMENTALS・RECONCILED・DC_TIMING がある（DC_TIMING の中に market_credit と construction_actuals の欄がある。値が取れなかった週は空でよい）。DC_TIMING.regulation.texas_pause.state と projects が埋まっているか見る。空なら収集エージェントに P1-7 の a・b を確認させる（1回まで））。
flags に adr_ratio_or_data_suspect があっても SKHY の ADS 比率は確認済み（0.1株、424B4）なので、終値の確認だけでよい。
月の最初の実行なら DRAM ETF の公式情報も確認。

## 3. 判定（第2段階）
別の Agent（general-purpose）に prompts/judge.md に完全に従わせる。
入力：handoff/latest.yaml、handoff/forecasts.csv、/home/claude/sd-data/ の各ファイル（［v1.5］sector_health.json・history_health.csv を含む）、evidence/latest.yaml、/home/claude/mkt_signals.json。
出力：reports/<日付>.md、handoff/latest.yaml と handoff/<日付>.yaml、forecasts.csv の追記・判定更新。
期限が来た予測（forecasts.csv の open で deadline 経過）を必ず判定させる。

## 4. 点検（自分で）
- handoff/latest.yaml が読める。LEVELS.S/D が /home/claude/sd-data/levels.json と一致。SCENARIOS 各期間の合計が100。
- FORECASTS.new が forecasts.csv にある。
- MARKET_CONTEXT が /home/claude/mkt_signals.json の値と一致し（先導セクター・ヘッジ・長期モデルの項目を含む）、反転リスク「テック内部の崩れ」の状態が judge.md 判定基準5節の規則どおり。
- 報道値（reported_unverified）と XBRL 未反映の値（pending_xbrl）に本文で「要確認」が付き、UNCONFIRMED_ITEMS に残っている。RECONCILED の mismatch が0節に書かれている。
- 冒頭ブロック（今日のひとこと3行＝半導体／メモリー／行動の目安、＋なぜその判断か）がある。本文の状態語が言葉→数字（記号）の形になっている。
- （v1.3）LEVELS.A の A4・A5 が数値（−2〜+2）になっている（除外なら0節に「DC_TIMING なし」の理由がある）。6a節に5つの見出しと scenario_lean がある。YAML に DC_TIMING と DOWNSTREAM_RS があり、反転リスク「米国内のDC規制・許認可」「AI投資の資金調達・信用」の状態が本文10節に書かれている。12節に政策の固定日程の表がある。
- （v1.5）4d節とYAMLの SECTOR_HEALTH が /home/claude/sd-data/sector_health.json の値と一致している（label、risk.count、washout.count、washout.phase の code・anchor_date・close_vs_anchor_pct、strip の緑の数と state。再計算していない）。そろい数が3未満で局面が none 以外のとき「まだ売られ尽くしていない」と書いていない。「過去5回で外れなし」「だまし0%」と書いていない。帯・危険の目安・底の目安が採点（LEVELS）・VIEW・行動の目安の「買え」「売れ」に使われていない。底の目安が3つそろった最初の週（初回は 2026-11-05 の分）は FORECASTS.new に26週の予測がある。sector_health.json が無い・古いときは4d節が「未取得」になっている。
- （v1.8）冒頭ブロックの「半導体」「メモリー」の行が、株価の状態と市況の見方を分けて書いている（judge.md v6.9。「やや強気」などのラベルだけで行を始めていない。値動きの点数が30未満、または反転リスクの発動が2つ以上の週は、株価の状態が先）。
- （v1.8）10a節（需給と信用の市場の値）があり、YAML に FLOWS_CREDIT がある。①買い戻しの燃料は market-data の reports/flows/fuel_latest.yaml の値と一致（再計算していない。読めない週は「未取得」）、②の HY・CCC は /home/claude/sd-data/semis_manifest.json の macro.latest の値。10a節の値が採点（LEVELS）・反転リスクの段階・シナリオ確率に使われていない。
- （v1.8）倍率に基準（20日平均・50日平均）が書かれ、4d節で簡易版の割合を「上昇中」「下落中」と書いていない。
不一致は判定エージェントに差し戻す（最大2回）。

## 5. 保存
`git add -A` → commit「report <日付>」→ `git push origin main`。data ブランチには書かない。
［v1.7］push が断られたとき：
  ・「fetch first」「non-fast-forward」と出た（ほかの更新が先に入っただけで、権限の問題ではない）→ `git pull -q --rebase origin main` のあと、もう一度 push する。
  ・それ以外（403 など、書き込みが許可されていない）→ このときだけ ToolSearch（query: "add_repo"）で名前が add_repo で終わるツールを探し、見つかれば
    add_repo（owner: "bakaho19920625-wq", repo: "semis-data", access: "push"）を呼んでから、同じ push をもう1回だけ試す。
    それでも断られたら、エラー文をそのまま控え、配信の最後に「GitHub に保存できませんでした：（エラー文）」と1行で書く（推測で原因を書かない）。レポートの配信は続ける。
  ・push が実際に断られたとき以外は、add_repo・gh・書き込みの道具の状態を、レポートにも配信にも書かない（何も送らず終了する回でも同じ）。
［v1.9］読む用の保管ページ「半導体・メモリー 週次定点観測」（https://claude.ai/artifact/8yev96zRruPECPTdCEu7P8）への保存。週次定点観測だけが基準日の新しい順に並ぶ、読むためのページ（ユーザー専用・非公開の Artifact）。GitHub への push のあとに行う：
1. `python3 /home/claude/semis-data/tools/archive_doc.py semis_weekly --recent 4`
   （reports/ の新しい4本について、/home/claude/archive_docs/semis_weekly/ に <id>.meta.json と <id>.body.json を作り、id とファイルの場所の一覧を表示する。id はレポートの日付 YYYY-MM-DD。本文は変えない。どこにも送らない。リポジトリの外に作るので git add -A には入らない）。
2. ArtifactData（道具の一覧に無ければ ToolSearch の query: "select:ArtifactData" で読み込む）の query（url は上のURL、collection: "reports"、query: {"order_by": {"field": "as_of", "direction": "desc"}, "limit": 30}）で、ページにすでにある id を読む。
3. 1 の一覧のうちページに無い id だけを、ArtifactData の batch（url は上のURL）で書く。1本につき2つ：
   {"op": "set", "collection": "reports", "doc_id": "<id>", "file_path": "<meta_file>"} と {"op": "set", "collection": "bodies", "doc_id": "<id>", "file_path": "<body_file>"}。
   今回の分と、過去に入れ損ねた分が一緒に入る。無いものが0本なら何も書かない。新しく作る文書なので if_version は要らない。
   すでにある id を書き直すとき（同じ日付の訂正版、補完の作り直し）だけ、その2つを get して version を読み、if_version を付けて set する。
4. 書けなかったとき（ArtifactData が見つからない場合を含む）は通知を増やさず、最後の返答に「読む用の保管ページに保存できませんでした」と1行書くだけでよい（次の回の 3 で自動的に入る。レポートの配信と GitHub への保存は続ける）。
   口座・保有・数量はこのページにも書かない（本文に無いので、本文をそのまま入れるかぎり入らない）。

## 6. 配信
［v1.8］SendUserMessage は**1画面**（日本語でおよそ800〜1,200字）。全文は添付の本文で読めるので、配信には判断に要るものだけを書く：
1. 冒頭ブロック（judge.md の「今日のひとこと」3行＋「なぜその判断か」をそのまま）
2. 前回から変わった点：総合点（帯）と前回比、段階が変わった小項目（drivers）の上位3、反転リスクで状態が変わったものと発動中のもの（「テック内部の崩れ」「米国内のDC規制・許認可」「AI投資の資金調達・信用」は状態を必ず1語で）、予測の判定結果と累積の的中率
3. 1行ずつ：セクターの状態（4d節：公式ステージの分布と判定、危険の目安 n/3、底の目安 n/3 と底の局面。売買の合図ではない言い方で）／需給と信用（10a節：燃料の棒と残り約○割、信用の1行、まとめ）／AIインフラの稼働タイミング（6a節の scenario_lean。状態が変わった週は規制の状態と後ろ倒しの件数も）
4. 次回の監視項目3つと、データ監査で伝えるべきこと（未更新・取得失敗・要確認の多い項目。なければ書かない）
6カテゴリの内訳、S/D の小項目、市場全体とテック内部（4c節）の詳細、シナリオ確率の表は配信に書かない（本文にある。前回から変わった週だけ2の中で1行）。最後に「全文は添付のファイルと、保管ページ（これまでの週次が並ぶ）：https://claude.ai/artifact/8yev96zRruPECPTdCEu7P8」と1行（［v1.9］このリンクは毎回出す）。
reports/<日付>.md を SendUserFile で送る。

## 7. 欠けた週の補完（v1.4。土曜の定期実行が動かなかった週の週次を後日作る）
- きっかけ：日次の冒頭の警告（先週の週次が未作成）か、ユーザーの「半導体の週次を補完して」。自動では作らない。
- 基準日 D：欠けた週の金曜（休場なら最後の取引日）。/home/claude/sd-data を D 時点に戻す：`cp` で作業用ディレクトリに複製し、
  `python3 build_snapshot.py --out <dir> --as-of D && python3 build_health.py --out <dir> --as-of D && python3 build_signals.py --out <dir> --as-of D`（levels.json・semis_manifest.json・daily_signals.json・resilience.json・［v1.5］sector_health.json が D 時点の値になる）。
  米国株側の signals.json は market-data の `analyze.py --as-of D --replay-ledger 130`（daily_runbook 第8節）で D 時点の値を作る。
- 収集（第2節）と判定（第3節）は通常どおり2段階で行う。収集エージェントには「市場基準日は D。D より後に公表された決算・統計・報道は使わない（D 時点で分かっていたことだけ）」と伝える。
  判定エージェントには「D 時点の levels.json（複製側）に LEVELS を一致させる」「予測の期限は D 基準」と伝える。
- タイトルに「（補完版）」、0節に「この週の週次は配信できなかったため、後日 D 時点のデータで作り直したもの」と書く。
- 保存は第5節と同じ（commit「report D (backfill)」）。handoff/latest.yaml は、補完した週より新しい週次がすでにあるなら上書きしない（handoff/D.yaml だけ置く）。forecasts.csv には追記する。
  ［v1.9］読む用の保管ページにも入れる（第5節の手順 1〜3。補完した週が新しい4本に入らないときは、手順1を `--id D` に替えてその1本を作る）。配信の最後に第6節と同じ保管ページの1行。

