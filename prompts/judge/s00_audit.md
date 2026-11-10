# 週次（判定）｜0. データ監査
# prompts/judge.md の「ひな形」の表から、この節を書く直前に読む。

- 見出し：`## 0. データ監査`
- 基準日、run_status、品質フラグへの対応、Webで補った値、未確認、定義変更の有無、証拠YAMLの予算消化、機械取得の実績値（DATA_NOTES.machine_generated／machine_source_kind／machine_status、MACHINE_FUNDAMENTALS の companies_ok と sec_checks の結果）と RECONCILED の結果、market-data signals.json の基準日と definition_version
- 0節（データ監査）は15行まで：問題のない項目は「問題なし」と1行にまとめ、対応が要るもの・前回と違うものだけ個別に書く。
- 末尾に「点検：R1～R15、C1～C14 確認」と書く（judge.md「書き終えたら」の自己点検を済ませてから）。
- judge.md の「データ監査」で分かったこと（データ未更新、基準日の違い、旧版の項目、「DC_TIMING なし」、RECONCILED の mismatch）は、ここに書く。
