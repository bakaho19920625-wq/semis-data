# 10. データ監査

- 見出し：`### 10. データ監査`
- 分量：2〜3行。
- 流れの側でデータ更新を起動した日は、その旨を書く（「伝えておくこと」で知らされる）。
基準日、価格を取得した時刻（`prices_manifest.json` の generated_utc）、run_status（`health`・`rebound` を含む）、フラグ（stale/jump/adr）、取引時間中に捨てた足（`unclosed_dropped` の rows が0でない日だけ）、Webで補った値、確認回数。
問題のない項目は「問題なし」とまとめ、対応が要るものだけ個別に書く。
market-data signals.json の基準日（as_of_market_date）と definition_version。
