# 半導体・メモリー定点観測｜週次の定期実行 手順（schedule_weekly v1.6。v1.6＝点検・配信に底の局面（judge v6.8）。v1.3＝証拠 v7.2（DC_TIMING）・判定 v6.6（A4・A5、反転リスク2項目、6a節）対応。v1.4＝14:11 の再試行の重複防止、欠けた週の補完（第7節）。v1.5＝判定 v6.7 対応：点検・配信・補完に sector_health.json（セクターの状態、4d節・SECTOR_HEALTH）を追加）
# 定期実行（スケジュールタスク。土曜 10:11 JST、利用上限などで動けなかったときの再試行 14:11。会話の記憶がない新しいセッションで動く）の本文は、このファイルを読む指示だけ。手順を変えるときはこのファイルを直す。
# 収集は prompts/collector.md、判定は prompts/judge.md が正本。ここは「準備・2段階の回し方・点検・保存・配信」の段取りだけ。

## 1. 準備
- /home/claude/semis-data がなければ add_repo（owner=bakaho19920625-wq、repo=semis-data、access=push）のあと
  `git clone --depth 1 https://github.com/bakaho19920625-wq/semis-data /home/claude/semis-data`。あれば `git -C /home/claude/semis-data pull -q`。
- data ブランチ：`rm -rf /home/claude/sd-data && git clone -q --depth 1 --branch data https://github.com/bakaho19920625-wq/semis-data.git /home/claude/sd-data`
- 米国株指標チェックの判定結果（judge.md 4c節・MARKET_CONTEXT・反転リスク「テック内部の崩れ」に転記するだけで、採点には使わない）：
  `curl -sSf https://raw.githubusercontent.com/bakaho19920625-wq/market-data/data/signals.json -o /home/claude/mkt_signals.json`
  届かなければ `rm -rf /home/claude/mkt-data && git clone -q --depth 1 --branch data https://github.com/bakaho19920625-wq/market-data.git /home/claude/mkt-data`。
- semis_manifest.json の us_as_of を日付ラベル YYYY-MM-DD にする。直近の米国取引日より古ければ「GitHubデータ未更新」と明記して続行。
- ［v1.4］同じ日付の週次がすでにある（reports/<日付>.md があり、handoff/latest.yaml の REPORT_DATE が同じ）なら、何も送らず終了する（14:11 の再試行が 10:11 の成功日に二重に作らないため）。

## 2. 収集（第1段階）
Agent（general-purpose）に prompts/collector.md に完全に従わせる。参照は docs/sources.md、/home/claude/sd-data/semis_manifest.json、
/home/claude/sd-data/fundamentals_latest.json（機械取得の実績値と SEC 確認用URL。collector.md 第2節）、handoff/latest.yaml、前回の evidence/latest.yaml（突き合わせ用。上書きする前に読ませる）。
run_status.json の fundamentals が failure、または fundamentals_latest.json の status が failed なら、その旨を収集エージェントに伝え（値は前回のまま）、実績値は従来どおりWebで探させる。
出力は evidence/<日付>.yaml と evidence/latest.yaml（yaml.safe_load で読めることを確認。EVIDENCE_VERSION: v7.2、MACHINE_FUNDAMENTALS・RECONCILED・DC_TIMING がある。DC_TIMING.regulation.texas_pause.state と projects が埋まっているか見る。空なら収集エージェントに P1-7 の a・b を確認させる（1回まで））。
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
不一致は判定エージェントに差し戻す（最大2回）。

## 5. 保存
`git add -A` → commit「report <日付>」→ `git push origin main`。data ブランチには書かない。

## 6. 配信
SendUserMessage で1〜2画面：冒頭ブロック（judge.md の「今日のひとこと」3行＋「なぜその判断か」をそのまま）、総合点（帯）と6カテゴリ内訳、S/D、前回比と drivers、予測の判定結果と累積の的中率、
反転リスク（「テック内部の崩れ」「米国内のDC規制・許認可」「AI投資の資金調達・信用」の状態と根拠を含む）、AIインフラの稼働タイミング（6a節の要点：規制の状態、後ろ倒しの件数、scenario_lean の1行）、［v1.5］セクターの状態（4d節の要点1〜2行：判定ラベルと前回比、危険の目安 n/3、底の目安 n/3 と底の局面、帯の状態。売買の合図ではない言い方で）、市場全体とテック内部（4c節の要点2行。先導セクターと半導体の先導株数、ヘッジ条件、長く持つ分の目安を含む）、次回の監視項目3つ、データ監査の要点。
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

