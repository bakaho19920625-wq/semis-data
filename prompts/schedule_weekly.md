# 半導体・メモリー定点観測｜週次の定期実行 手順（schedule_weekly v1.0）
# 定期実行（send_later。土曜 10:11 JST）の本文は、このファイルを読む指示だけ。手順を変えるときはこのファイルを直す。
# 収集は prompts/collector.md、判定は prompts/judge.md が正本。ここは「準備・2段階の回し方・点検・保存・配信」の段取りだけ。

## 1. 準備
- /home/claude/semis-data がなければ add_repo（owner=bakaho19920625-wq、repo=semis-data、access=push）のあと
  `git clone --depth 1 https://github.com/bakaho19920625-wq/semis-data /home/claude/semis-data`。あれば `git -C /home/claude/semis-data pull -q`。
- data ブランチ：`rm -rf /home/claude/sd-data && git clone -q --depth 1 --branch data https://github.com/bakaho19920625-wq/semis-data.git /home/claude/sd-data`
- 米国株指標チェックの判定結果（judge.md 4c節・MARKET_CONTEXT・反転リスク「テック内部の崩れ」に転記するだけで、採点には使わない）：
  `curl -sSf https://raw.githubusercontent.com/bakaho19920625-wq/market-data/data/signals.json -o /home/claude/mkt_signals.json`
  届かなければ `rm -rf /home/claude/mkt-data && git clone -q --depth 1 --branch data https://github.com/bakaho19920625-wq/market-data.git /home/claude/mkt-data`。
- semis_manifest.json の us_as_of を日付ラベル YYYY-MM-DD にする。直近の米国取引日より古ければ「GitHubデータ未更新」と明記して続行。

## 2. 収集（第1段階）
Agent（general-purpose）に prompts/collector.md に完全に従わせる。参照は docs/sources.md、/home/claude/sd-data/semis_manifest.json、handoff/latest.yaml。
出力は evidence/<日付>.yaml と evidence/latest.yaml（yaml.safe_load で読めることを確認）。
flags に adr_ratio_or_data_suspect があっても SKHY の ADS 比率は確認済み（0.1株、424B4）なので、終値の確認だけでよい。
月の最初の実行なら DRAM ETF の公式情報も確認。

## 3. 判定（第2段階）
別の Agent（general-purpose）に prompts/judge.md に完全に従わせる。
入力：handoff/latest.yaml、handoff/forecasts.csv、/home/claude/sd-data/ の各ファイル、evidence/latest.yaml、/home/claude/mkt_signals.json。
出力：reports/<日付>.md、handoff/latest.yaml と handoff/<日付>.yaml、forecasts.csv の追記・判定更新。
期限が来た予測（forecasts.csv の open で deadline 経過）を必ず判定させる。

## 4. 点検（自分で）
- handoff/latest.yaml が読める。LEVELS.S/D が /home/claude/sd-data/levels.json と一致。SCENARIOS 各期間の合計が100。
- FORECASTS.new が forecasts.csv にある。
- MARKET_CONTEXT が /home/claude/mkt_signals.json の値と一致し（先導セクター・ヘッジ・長期モデルの項目を含む）、反転リスク「テック内部の崩れ」の状態が judge.md 判定基準5節の規則どおり。
- 冒頭ブロック（今日のひとこと3行＝半導体／メモリー／行動の目安、＋なぜその判断か）がある。本文の状態語が言葉→数字（記号）の形になっている。
不一致は判定エージェントに差し戻す（最大2回）。

## 5. 保存
`git add -A` → commit「report <日付>」→ `git push origin main`。data ブランチには書かない。

## 6. 配信
SendUserMessage で1〜2画面：冒頭ブロック（judge.md の「今日のひとこと」3行＋「なぜその判断か」をそのまま）、総合点（帯）と6カテゴリ内訳、S/D、前回比と drivers、予測の判定結果と累積の的中率、
反転リスク（「テック内部の崩れ」の状態と根拠の数値を含む）、市場全体とテック内部（4c節の要点2行。先導セクターと半導体の先導株数、ヘッジ条件、長く持つ分の目安を含む）、次回の監視項目3つ、データ監査の要点。
reports/<日付>.md を SendUserFile で送る。
