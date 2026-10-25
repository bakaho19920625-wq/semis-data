# 情報源マップ（docs/sources.md）

収集プロンプトが最初に1回読む参照資料。数値は再利用せず、毎回最新ページで確認する。

情報源の優先順位と参照先を固定するものです。ここに書いた数値は再利用せず、レポートのたびに最新のページで確認します。

## 1. 市場データ（GitHub：semis-data）
- リポジトリ：https://github.com/bakaho19920625-wq/semis-data
- dataブランチ（自動更新。米国の営業日の翌朝7:27 JST、火～土）：土日と月曜早朝のレポートは直近金曜の終値になる
- mainブランチの `handoff/`：レポート間の引継ぎ（手動またはClaudeのコミットで更新）
- 元データ：Yahoo Finance（yfinance経由の非公式な取得）、FRED

### 経路A：シェルが使える環境
`git clone -q --depth 1 --branch data https://github.com/bakaho19920625-wq/semis-data.git md`
引継ぎ・証拠・プロンプトは main ブランチ：`git clone -q --depth 1 https://github.com/bakaho19920625-wq/semis-data.git hs`（`hs/handoff/`、`hs/evidence/`、`hs/prompts/`）。

### 経路B：Web取得のみの環境（raw URL）
- https://raw.githubusercontent.com/bakaho19920625-wq/semis-data/data/run_status.json
- https://raw.githubusercontent.com/bakaho19920625-wq/semis-data/data/semis_manifest.json
- https://raw.githubusercontent.com/bakaho19920625-wq/semis-data/data/levels.json
- https://raw.githubusercontent.com/bakaho19920625-wq/semis-data/data/semis_snapshot.csv
- https://raw.githubusercontent.com/bakaho19920625-wq/semis-data/data/history_key.csv
- https://raw.githubusercontent.com/bakaho19920625-wq/semis-data/data/history_levels.csv
- https://raw.githubusercontent.com/bakaho19920625-wq/semis-data/data/adr_premium.csv
- https://raw.githubusercontent.com/bakaho19920625-wq/semis-data/data/macro_daily.csv
- https://raw.githubusercontent.com/bakaho19920625-wq/semis-data/main/handoff/latest.yaml
- https://raw.githubusercontent.com/bakaho19920625-wq/semis-data/main/handoff/forecasts.csv
- https://raw.githubusercontent.com/bakaho19920625-wq/semis-data/main/evidence/latest.yaml
（`prices_daily.csv.gz` は圧縮ファイルのため経路Bでは読めない）

| ファイル | 中身 |
|---|---|
| run_status.json | 直近の実行で各ステップが success か failure か。failure のファイルは前回のまま |
| semis_manifest.json | 最初に読む。基準日（us_as_of）、欠損銘柄、品質フラグ、S/Dスコア、騰落の広がり、ADR要約、マクロ最新値 |
| levels.json | S1～S5・D1～D6の段階と入力値、S/D/TECHNICALスコア、coverage |
| semis_snapshot.csv | 銘柄ごとの最新指標（定義は判定基準0節） |
| history_key.csv | 主要銘柄の終値・SMA・RSI等の日次履歴（前回比に使う） |
| history_levels.csv | 段階とスコアの日次履歴 |
| adr_premium.csv | SKHYの理論ADS価値とプレミアムの推移（直近60営業日） |
| macro_daily.csv | DGS10、DFII10、DTWEXBGS（FRED） |

- 終値・テクニカルの第1ソースはこのデータとし、商品ごとにソースを変えません。
- 欠損・品質フラグがある値だけWebで補い、出典と確認日時を付けます。

## 2. Web情報源の優先順位
1. 企業IR、SEC、ETF運用会社、指数提供会社、取引所、政府・中央銀行、標準化団体
2. TrendForce/DRAMeXchange、WSTS、SEMI、SIA、Omdia、TechInsights等の専門調査・分解解析
3. Reuters、Bloomberg、FT、WSJ等の主要報道
4. その他の市場データ・集計
5. SNS、X、YouTubeは発見用途のみ。原資料まで遡る

有料資料は利用権限がある場合のみ使います。検索スニペットだけで結論を作りません。下のURLが開けない場合は、検索で同じ発行元の最新ページを探し、2回試して取れなければ「未確認」として先へ進みます。

## 3. 指数・ETF公式
- SOX（Nasdaq）：https://indexes.nasdaqomx.com/Index/Overview/SOX
- SOXX（iShares）：https://www.ishares.com/us/products/239705/ishares-phlx-semiconductor-etf
- SMH（VanEck）：https://www.vaneck.com/us/en/investments/semiconductor-etf-smh/
- SOXL（Direxion）：https://www.direxion.com/product/daily-semiconductor-bull-bear-3x-etfs
- SPY（State Street）：https://www.ssga.com/us/en/intermediary/etfs/spdr-sp-500-etf-trust-spy
- QQQ（Invesco）：https://www.invesco.com/qqq-etf/en/home.html
- DRAM（Roundhill）：https://www.roundhillinvestments.com/etf/dram/ ／Cboe：https://www.cboe.com/us/equities/listings/listed_products/symbols/DRAM/ ／SEC EDGAR：https://www.sec.gov/edgar/search/
  - 月1回確認：運用方針、主市場、設定日、経費率、NAV乖離、スプレッド、AUM、口数、最新保有と基準日、上位集中、国別・製品別構成、現物・預託証券・優先株・swap・T-Billの構成、目論見書の変更、分配・分割・ティッカー変更。純流入は確認元がなければ未確認。

## 4. ADR・韓国市場・為替
- SK hynix IR：https://www.skhynix.com/ir/UI-FR-IR01/ ／Newsroom：https://news.skhynix.com/
- SEC EDGAR（F-1、424B4、F-6、6-K等）：https://www.sec.gov/edgar/browse/?CIK=0002120882
- Nasdaq SKHY：https://www.nasdaq.com/market-activity/stocks/skhy ／Korea Exchange：https://global.krx.co.kr/
- ADS比率：1 ADS＝普通株0.1株（2026年7月の424B4。預託銀行はCitibank, N.A.）。`adr_ratio_or_data_suspect` が出たら6-K・F-6で変更を確認する。
- Samsung IR：https://www.samsung.com/global/ir/ （普通株と優先株を混同しない）
- Bank of Korea：https://www.bok.or.kr/eng/main/main.do

## 5. マクロ公式
FRED：https://fred.stlouisfed.org/ ／Federal Reserve：https://www.federalreserve.gov/ ／米財務省（金利）：https://home.treasury.gov/resource-center/data-chart-center/interest-rates ／BLS：https://www.bls.gov/ ／BEA：https://www.bea.gov/ 。CME FedWatchは市場予想の補助でありFRBの公式ではない。

## 6. 企業IR・規制資料
- AI・ロジック：NVIDIA https://investor.nvidia.com/ ／NVIDIA Developer Blog https://developer.nvidia.com/blog/ ／AMD https://ir.amd.com/ ／Broadcom https://investors.broadcom.com/ ／TSMC https://investor.tsmc.com/ ／Intel https://www.intc.com/
- メモリー・ストレージ：Micron https://investors.micron.com/ ／Kioxia Holdings https://www.kioxia-holdings.com/en-jp/ir.html ／Kioxia XL-FLASH https://www.kioxia.com/ja-jp/business/memory/xlflash.html ／SanDisk https://investor.sandisk.com/ ／Solidigm https://www.solidigm.com/ ／Nanya https://www.nanya.com/en/IR ／Winbond https://www.winbond.com/hq/about-winbond/investor/investor-conference/?__locale=en
- 装置・後工程：ASML https://www.asml.com/en/investors ／Applied Materials https://ir.appliedmaterials.com/ ／Lam Research https://investor.lamresearch.com/ ／KLA https://ir.kla.com/ ／ASE https://www.aseglobal.com/ ／Amkor https://ir.amkor.com/
- ハイパースケーラー：Microsoft https://www.microsoft.com/en-us/Investor ／Alphabet https://abc.xyz/investor/ ／Amazon https://ir.aboutamazon.com/ ／Meta https://investor.atmeta.com/ ／Oracle https://investor.oracle.com/

## 7. メモリー市況・業界統計
TrendForce/DRAMeXchange、WSTS、SEMI、SIA、Omdia、TechInsights。スポットか契約か、期間、容量、製品規格を明記し、専門調査の推定と企業の開示を混同しない。

## 8. 標準化団体・メモリー階層
- JEDEC https://www.jedec.org/ ／CXL Consortium https://computeexpresslink.org/ ／UCIe Consortium https://www.uciexpress.org/ ／Open Compute Project https://www.opencompute.org/
- HBF：SK hynix https://news.skhynix.com/en/hbf-at-fms-2026/ ／SanDisk https://investor.sandisk.com/news-releases ／OCPの仕様・ワークストリームを優先
- CXLは仕様・white paperで memory pooling/sharing、fabric、実装段階を確認。CPO・光I/OはNVIDIAやネットワーク機器メーカーの公式資料で帯域、電力、量産時期を確認。SRAM中心アクセラレーターはCerebras、Groq、Tenstorrent等の公式資料で外部メモリー、対象ワークロード、出荷・顧客採用まで確認。

## 9. 分解・部品表
優先順位：メーカー公式のBOM・規制資料・部品番号 → 複数の独立した専門分解 → TechInsights等の分解解析 → iFixit、EE Times/TechanaLye等の公開分解 → ダイ写真・面積からの推定 → リーク・SNS

## 10. 技術・論文
優先順位：原論文 → 採択会議・学術誌 → 著者・研究機関 → 企業の公式実装 → 独立再現 → 報道・SNS

## 11. 引用・データ日のルール
- 数値の直後か同じ段落に出典を書く。データ対象日、発表日、確認日を区別する。ETFの保有には基準日を付ける。
- 企業のガイダンスと市場コンセンサスを分ける。現在値と過去値を混在させない。
- 取得できないものは「未確認」、企業が開示していないものは「非開示」とする。
- ADRと現地株の比較では、価格の時刻、ADS比率、為替の時刻を明記する。
