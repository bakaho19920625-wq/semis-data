# 監視ユニバース・KPI（docs/universe_kpi.md）

詳細なKPI一覧。収集プロンプトのP1/P2に出てこない細かい確認項目が必要なときだけ読む。

「何を継続観測するか」と「どこから取るか」を固定する基準書です。最新値や保有比率は書き込まず、レポートのたびに再確認します。判定の仕方は「判定基準・スコアリング」にあります。

取得先の略号
- GH：GitHubリポジトリ semis-data のdataブランチ。終値・テクニカル・相対強度・騰落の広がり・ADRプレミアム・金利・ドル指数・S/Dの段階
- Web：決算、ガイダンス、月次売上、価格調査、ETFの公式情報、ニュース

## 1. 市場・ETF・上場商品（すべてGH。Yahooティッカーは tickers.txt を正とする）

| 区分 | 対象 | 役割 |
|---|---|---|
| 米国株全体 | S&P 500（^GSPC）、SPY | 景気・流動性・リスク選好の基準 |
| 大型テック | QQQ | AI・大型成長株の比較基準 |
| 半導体指数 | SOX（^SOX） | 半導体セクター全体（出来高なし） |
| 半導体ETF | SOXX、SMH | SOXLに近い非レバETF／大型集中型 |
| メモリーETF | DRAM（Roundhill Memory ETF） | メモリー・ストレージ株の市場期待とポジショニング |
| メモリー米国株 | MU、SNDK、SKHY、WDC、STX | 米国時間のメモリー・ストレージ株 |
| メモリー現地株 | SK hynix（000660.KS）、Samsung普通株（005930.KS）、Kioxia（285A.T）、Nanya（2408.TW）、Winbond（2344.TW） | 原資産・地域市場・為替 |
| レバETF | SOXL | 日次3倍商品の過熱・経路依存性 |
| リスク | VIX | 短期不安 |
| 金利・ドル | ^TNX、FRED DGS10（名目）、DFII10（実質）、DTWEXBGS（ドル指数） | バリュエーションと資本コスト |
| 為替 | USD/JPY、USD/KRW | 円換算、韓国株とADSの比較 |

Samsungの優先株は必要な場合だけWebで確認し、普通株と混同しません。

## 2. DRAM ETF
- 基本：Roundhill Memory ETF、ティッカー DRAM、アクティブ運用。HBM、DRAM、NAND/SSD、NOR、HDD、specialty/embedded memory等の関連企業に投資。現物株、預託証券、優先株、total return swap、現金・T-Bill等を使う場合がある。
- 位置づけ：メモリー・ストレージ株の価格期待、テーマ資金、相対モメンタムを見る市場指標。DRAM契約価格・スポット価格・HBM価格・bit需要の指数ではない。
- テクニカルKPI（GH、毎回）：終値、騰落率、運用期間、SMA20/50/200と乖離率、RSI14、出来高比、上昇/下落出来高比、高値からの下落率、実現ボラ、対SOXX・対SPY相対強度、D1～D6の段階
- ファンドKPI（Web、月1回またはflags発生時）：保有銘柄と基準日、AUM、口数、NAV乖離、30日中央値スプレッド、上位3・5銘柄と国別の集中度、HBM/DRAM・NAND/SSD・HDD等の概算構成、現物・預託証券・swap・T-Billの構成、純流入（確認元がある場合のみ）、運用方針・デリバティブ使用の変更

## 3. メモリー投資手段・市場構造
- 比較対象：DRAM ETF、MU、SKHYと韓国普通株、Samsung、Kioxia、SNDK
- KPI：メモリー売上・利益への純度とHBM/DRAM/NAND/HDDの事業mix（Web）、上場市場・通貨・流動性・スプレッド（Web）、ETF経費とデリバティブ・カウンターパーティーリスク（Web）、ADS比率・預託手数料・発行転換の制約（Web）、理論ADS価値とプレミアム（GH：adr_premium.csv）、米国時間とアジア市場の時差、DRAM ETF内の重複（Web）

## 4. AIアクセラレーター・ASIC（Web）
対象：NVIDIA、AMD、Broadcom、Marvell、クラウド各社の自社ASIC、必要に応じCerebras、Groq、Tenstorrent等
KPI：データセンター売上・成長率・粗利益率、GPU/ASICの出荷・ASP・製品mix・backlog・納期、学習/prefill/decodeの需要内訳、HBMの搭載量・帯域・世代・サプライヤー構成、オンダイSRAM容量と外部メモリー構成、新製品移行時の需要空白・在庫、AIサービス売上・顧客ROI・稼働率

## 5. ファウンドリー・先端ロジック（Web）
対象：TSMC、Intel、Samsung Electronics
KPI：月次売上（単月と3か月累計の前年比）、先端ノード売上比率、稼働率、ウェハー価格、顧客在庫、歩留まり、量産時期、顧客認定、CoWoS等の先端パッケージ能力と地域別増強、SRAM増加によるロジックダイ面積・チップレット需要、AI/HPC・スマホ・PC・自動車の需要構成

## 6. 半導体製造装置（Web）
対象：ASML、Applied Materials、Lam Research、KLA
KPI：受注、backlog、出荷、WFE、ロジック/DRAM/NAND向け投資、中国比率、規制、リードタイム、EUV/High-NA、成膜、エッチング、検査、投資の延期・前倒し

## 7. メモリー企業・供給監視（Web）
- 中核：Micron、Samsung Electronics、SK hynix、Kioxia、SanDisk。SolidigmはSK hynix傘下のenterprise SSD事業として確認する。
- legacy・供給側：Nanya、Winbond。CXMT・YMTCは公開情報の範囲で供給能力、技術移行、価格影響を監視する。
- KPI：bit shipment、bit growth、ASP、売上、粗利益率、営業利益、在庫日数・金額、稼働率、wafer投入、die/wafer、歩留まり、bit/die、bit density、層数、string stacking、製品mix、CAPEXと投資対象、顧客認定・長期契約・前払い・供給コミット、パッケージ・コントローラ・基板等の制約
- DRAMの分類：HBM3E/HBM4以降、server DRAM/DDR5、mobile LPDDR5/5X、legacy（DDR4、LPDDR4/4X、specialty）、特殊需要（車載、産業、ネットワーク、モデム等）
- NANDの分類：SLC/MLC、TLC、QLC、PLC、HBF・XL-FLASH/SCM、client/mobile、enterprise SSD、HDD代替

## 8. ハイパースケーラー（株価はGH、KPIはWeb）
対象：Microsoft、Alphabet、Amazon、Meta、Oracle
KPI：CapExの実績・ガイダンス（4社合計の前年比を毎回記録）、AI向け比率、GPU/ASIC調達、データセンター建設、電力・冷却、減価償却、AI売上・受注・収益化、CapEx回収速度

## 9. 光通信・ネットワーク・メモリー階層（株価はGH、KPIはWeb）
対象：LITE、COHR、ANET、AVGO、CRDO、ALAB、CPO/シリコンフォトニクス、CXL、UCIe、HBF、SCM、GPU直結SSD等
KPI：800G/1.6T、光トランシーバー、レーザー、DSP、CPO、scale-up/scale-outの帯域・遅延・消費電力・到達距離、CXLのメモリープーリング/共有、HBM容量・帯域とローカルDRAM・共有DRAM・HBF/SCM・eSSD・HDDの役割、KVキャッシュ・モデル重み・活性値・勾配・チェックポイントの配置、1アクセラレーター当たりHBMと業界総HBMビット需要の区別

## 10. AI効率化・アーキテクチャ（Web）
対象：EGGROLL、量子化、蒸留、LoRA、MoE、sparse attention、KVキャッシュ圧縮、再帰型モデル、SSDオフロード、SRAM中心アクセラレーター等
KPI：原論文・査読・独立再現、比較対象とモデル規模、pre-training/fine-tuning/推論、prefill/decodeの別、throughput、time-to-quality、総GPU時間、電力、ピークHBM容量・帯域、SRAM容量、外部メモリー、GPU台数、本番採用・顧客認定・量産・発注計画への実影響、1ジョブ当たりと業界総需要の区別
