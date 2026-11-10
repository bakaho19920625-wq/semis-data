# 情報源マップ（docs/sources.md）

収集プロンプトが最初に1回読む参照資料。情報源の優先順位と参照先を固定するもので、ここに書いた数値は再利用せず、レポートのたびに最新のページで確認する。

## 1. 市場データ（GitHub：semis-data）
- リポジトリ：https://github.com/bakaho19920625-wq/semis-data
- dataブランチ（自動更新。米国の営業日の翌朝 6:35 と 12:35 JST、火～土。前営業日の足が入るまで10分おきに取り直す）：土日と月曜早朝のレポートは直近金曜の終値になる
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
- https://raw.githubusercontent.com/bakaho19920625-wq/semis-data/data/resilience.json
- https://raw.githubusercontent.com/bakaho19920625-wq/semis-data/data/daily_signals.json
- https://raw.githubusercontent.com/bakaho19920625-wq/semis-data/data/macro_daily.csv
- https://raw.githubusercontent.com/bakaho19920625-wq/semis-data/data/fundamentals_latest.json
- https://raw.githubusercontent.com/bakaho19920625-wq/semis-data/data/fundamentals.csv
- https://raw.githubusercontent.com/bakaho19920625-wq/semis-data/main/handoff/latest.yaml
- https://raw.githubusercontent.com/bakaho19920625-wq/semis-data/main/handoff/forecasts.csv
- https://raw.githubusercontent.com/bakaho19920625-wq/semis-data/main/evidence/latest.yaml
（`prices_daily.csv.gz` は圧縮ファイルのため経路Bでは読めない）

| ファイル | 中身 |
|---|---|
| run_status.json | 直近の実行で各ステップが success か failure か。failure のファイルは前回のまま |
| semis_manifest.json | 最初に読む。基準日（us_as_of）、欠損銘柄、品質フラグ、S/Dスコア、騰落の広がり、ADR要約、マクロ最新値 |
| levels.json | S1～S5・D1～D6の段階と入力値、S/D/TECHNICALスコア、coverage |
| semis_snapshot.csv | 銘柄ごとの最新指標（定義は build_snapshot.py の冒頭） |
| resilience.json | セクター内の強弱（sector_rs）と調整耐性（window、next_candidates、late_breaks）。定義は docs/sector_rs_resilience.md |
| daily_signals.json | 日次シグナル（変化点、主要銘柄の表、意識される水準、RS線）。日次レポートが読む |
| history_key.csv | 主要銘柄の終値・SMA・RSI等の日次履歴（前回比に使う） |
| history_levels.csv | 段階とスコアの日次履歴 |
| adr_premium.csv | SKHYの理論ADS価値とプレミアムの推移（直近60営業日） |
| macro_daily.csv | DGS10、DFII10、DTWEXBGS（FRED）。参考の系列として BAMLH0A0HYM2（HYスプレッド）、BAMLH0A3HYC（CCC格）、DGS2（2年金利。米国株指標チェックの日次が読む）。参考の系列は取れなくても status は変わらない |
| fundamentals_latest.json | 機械取得の四半期実績（40社：米国籍37社＋TSM・ASML・ARM）。売上・売上原価・在庫（在庫日数）・設備投資・営業CF と前年比・前期比、4社CapEx合計。通常は Yahoo の四半期財務（非公式・階層4）で、各社に SEC の XBRL で確認するためのURL `sec_check_urls` が付く。SEC に届く環境で動いた日は SEC の値（階層1）。収集プロンプト第2節 |
| fundamentals.csv | 同じ項目の全期間（四半期ごと1行。source 列が yahoo か sec_xbrl。derived=true は累計の差分で作った値） |

- 終値・テクニカルの第1ソースはこのデータとし、商品ごとにソースを変えません。
- 四半期実績（売上・在庫・設備投資）の第1ソースは fundamentals_latest.json。判断に効く数字（4社CapEx、メモリー3社の在庫・売上、NVDA売上）は同ファイルの sec_check_urls（SEC の XBRL API）で確認して階層1に格上げする。ガイダンス・ASP・ビット出荷・HBM比率は決算リリースや説明会資料（6節の IR）から。
- 欠損・品質フラグがある値だけWebで補い、出典と確認日時を付けます。

## 2. Web情報源の優先順位
1. 企業IR、SEC、ETF運用会社、指数提供会社、取引所、政府・中央銀行、標準化団体
2. TrendForce/DRAMeXchange、WSTS、SEMI、SIA、Omdia、TechInsights等の専門調査・分解解析
3. Reuters、Bloomberg、FT、WSJ等の主要報道
4. その他の市場データ・集計
5. SNS、X、YouTubeは発見用途のみ。原資料まで遡る

有料資料は利用権限がある場合のみ使います。検索スニペットだけで結論を作りません。下のURLが開けない場合は、検索で同じ発行元の最新ページを探し、2回試して取れなければ、3の主要報道が2本以上同じ数字を伝えているときに限り「報道値（reported_unverified）」として採用し、そうでなければ「未確認」として先へ進みます（収集プロンプト第4節）。

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
- ADS比率：1 ADS＝普通株0.1株（2026年7月の424B4。預託銀行はCitibank, N.A.。確認済み）。`adr_ratio_or_data_suspect` が出ても比率の再確認はせず、終値（ADSと原株）の整合だけ確認する（schedule_weekly 第2節）。比率の変更（6-K・F-6）を確認するのは年1回か、フラグが新たに立ったときだけ。
- Samsung IR：https://www.samsung.com/global/ir/ （普通株と優先株を混同しない）
- Bank of Korea：https://www.bok.or.kr/eng/main/main.do

## 5. マクロ公式
FRED：https://fred.stlouisfed.org/ ／Federal Reserve：https://www.federalreserve.gov/ ／米財務省（金利）：https://home.treasury.gov/resource-center/data-chart-center/interest-rates ／BLS：https://www.bls.gov/ ／BEA：https://www.bea.gov/ 。CME FedWatchは市場予想の補助でありFRBの公式ではない。

## 6. 企業IR・規制資料
- SEC EDGAR の公式API：XBRL https://data.sec.gov/api/xbrl/companyconcept/CIK##########/us-gaap/<タグ>.json（レポート側の WebFetch で読める。sec_check_urls はこの形）／提出一覧 https://data.sec.gov/submissions/CIK##########.json（大きすぎて WebFetch では途中で切れる）／提出書類の索引 https://www.sec.gov/Archives/edgar/data/<CIK>/<受理番号>/（読める。本文の .htm は読めないことがある）／全文検索 https://efts.sec.gov/LATEST/search-index?q=…（検索語だけ違うURLは1回の収集で1回しか正しく読めないので注意）。
  GitHub Actions（クラウドのIP）からは SEC 全体が 403「Undeclared Automated Tool」で拒否される（2026-11-02 確認）ため、機械取得は Yahoo で行い、SEC は確認に使う。CIK は config.json の fundamentals.cik
- AI・ロジック：NVIDIA https://investor.nvidia.com/ ／NVIDIA Developer Blog https://developer.nvidia.com/blog/ ／AMD https://ir.amd.com/ ／Broadcom https://investors.broadcom.com/ ／Marvell https://investor.marvell.com/ ／TSMC https://investor.tsmc.com/ ／Intel https://www.intc.com/
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

## 12. 米国内のデータセンター規制・許認可・稼働タイミング（収集プロンプト P1-7。判定の A4・A5、反転リスク「米国内のDC規制・許認可」「AI投資の資金調達・信用」）
優先順位は2節と同じ（1 州・連邦の公式 → 2 法律事務所の解説・専門調査 → 3 主要報道2本以上 → 4 その他）。選挙公約・陣営サイトは「公約（estimate）」であり行政措置ではない。就任後の行政命令・州機関への指示・法案だけを「措置」として記録する。
- テキサス州知事室（指示・命令のプレスリリース）：https://gov.texas.gov/news ／ 新知事の就任は 2027-01-19 予定（州憲法第4条。就任までの発言は公約扱い）
- ERCOT（大口接続 Batch Zero の分類、監査、知事指示の DC 監査結果の提出目標日 2026-12-10）：https://www.ercot.com/ （News・Grid Information から。報告は PUCT と連携）。データセンター影響の RFI：https://www.ercot.com/about/legal/data-center-impact-rfi
- PUCT（州公益事業委員会。議題・議事録）：https://www.puc.texas.gov/ ／ 会合の日程は ERCOT の公式カレンダー https://www.ercot.com/calendar/MMDDYYYY-PUCT-Meeting（2026-11-05 確認：11/19、12/17、2027-01-14、01/29）
  ※ 12/10 は ERCOT が監査結果を出す目標日で、承認・接続の決定日ではない（2026-11-05 に報道2本で確認。Texas Public Radio 2026-08-21、mgrid 2026-09-05）。ERCOT は Batch Zero の接続検討が 2027-04-09 の期限に間に合わないと公言しており、代替期限は未提示（同日確認）。日程が変わったら EVENTS_NEXT_14D で上書きする
- TCEQ（州環境当局。許認可停止の運用、電子申請の変更）：https://www.tceq.texas.gov/
- テキサス州議会（法案検索。通常会期は 2027-01-12 開会）：https://capitol.texas.gov/
- 連邦議会（公聴会・法案。新議会は 2027-01-03 正午）：https://www.congress.gov/ ／ 上院のエネルギー・商業委員会等は各委員会サイトの Hearings
- 他州の規制：各州の知事室・公益事業委員会・州議会の公式ページを検索で探す（州名＋ data center moratorium／utility commission）。報道だけなら reported_unverified
- 法律事務所の解説（措置の範囲・対象の整理に使う。階層2相当。数値の確定には使わない）：DLA Piper、Greenberg Traurig、Foley、Troutman 等の Insights を検索で
- 案件の進捗・資金（決算リリース・説明会資料・8-K/6-K を優先）：CoreWeave https://investors.coreweave.com/ ／ Nebius https://nebius.com/ （Investors）／ IREN https://iren.gcs-web.com/ ／ Galaxy Digital https://investor.galaxy.com/ ／ Vertiv https://investors.vertiv.com/ ／ Oracle は6節。社債の条件（金額・利率・年限・担保・償還開始）はプレスリリースか 8-K の Exhibit で確認する
- 3つの日付の定義：受電（energization）＝変電所・系統から電力を受け始めた日、引き渡し（delivery）＝顧客が使える状態で引き渡した日、課金開始（billing start）＝賃料・利用料の計上が始まった日。計画容量（GW/MW）・変電所の通電・建屋の完成・GPU設置は別の段階として書き分ける
- GPU レンタル価格：固定できる公式指標がないため、ネオクラウド決算の開示（平均単価・契約期間）と、主要報道2本以上が一致するスポット価格だけを使う。単一ブローカーの提示価格・SNS は使わない

## 13. 需給・信用の市場の値・DC建設の実績（追補 R1、2026-11-10。収集プロンプト P1-7 の f・g、判定の10a節、日次の2b・6b節）
- 買い戻しの燃料計（プロの持ち高の百分位、機械的な売りの見込み、自社株買いの解禁割合）：**半導体側では集めない**。米国株側（market-data）が週次と火曜の日次で更新する
  控え https://raw.githubusercontent.com/bakaho19920625-wq/market-data/main/reports/flows/fuel_latest.yaml を転記する。定義は market-data の `08_Addendum_v4.7_Flows_Fuel_VolTerm.txt`。
  元の掲載先（参考。2026-11-10 に実在を確認）：TheStreet Pro「The Week Ahead」（Goldman のプライムブック・CTA、Deutsche Bank の持ち高、Citadel の自社株買いをまとめる）、
  Tickmill ブログ「Institutional Insights」（Deutsche Bank／Goldman の週次の要約）、Investing.com の Deutsche Bank positioning の記事
- 信用の市場の値：CRWV・ORCL などの5年CDS、CRWV 2032年債（US$12.5億、表面利率9.625%）の利回りは、主要報道（CNBC、Yahoo Finance、Reuters、Bloomberg）の数字を使う。データの出どころは S&P Global Market Intelligence・LSEG など（記事に書かれたとおりに）。
  公式の無料の配信元はないので `reported_unverified`。確認済みの例：2026-10-15 ORCL 288bp（S&P Global・LSEG、Yahoo Finance）、CRWV 1,000bp超（LSEG）、2026-11-05 CRWV 1,289bp→11-06 約1,155bp・ORCL 約298bp・NVDA 約139bp・CRWV 2032年債 利回り16%超（24/7 Wall St.、出どころの記載なし）
- HYスプレッド・CCC格：FRED の BAMLH0A0HYM2・BAMLH0A3HYC（ICE BofA。`fetch_macro.py` が毎日取得し `macro_daily.csv` と manifest の macro.latest に入る。FRED 上の履歴は直近約3年）
- DC建設の実績：米国勢調査局 Construction Spending（C30）の民間・季節調整済み年率の表 https://www.census.gov/construction/c30/pdf/privsa.pdf の「Data center」の行（発表文は https://www.census.gov/construction/c30/pdf/release.pdf）。毎月第1営業日ごろに2か月前の月次。
  確認済みの例：2026年8月 年率849.5億ドル、前年比+73%（報道経由）。建物の建設費で、GPU 等の機器は含まない
- 戻りの質：Web は使わない。data ブランチ `rebound_quality.json`（`build_rebound.py`。定義と検証は docs/rebound_quality.md）
