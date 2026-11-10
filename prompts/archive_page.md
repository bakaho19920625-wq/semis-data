# 読む用の保管ページへの保存（半導体の日次・週次で共通）
# レポートだけが基準日の新しい順に並ぶ、読むためのページ（ユーザー専用・非公開の Artifact）。GitHub への push のあとに行う。

| 種類 | ページ | URL | 新しい本数 | レポートの場所 | id |
|---|---|---|---|---|---|
| semis_daily | 半導体・メモリー 日次レポート | https://claude.ai/artifact/RsGNScaBqUn628DmNiUcvX | 7 | reports/daily/ | レポートの日付 YYYY-MM-DD |
| semis_weekly | 半導体・メモリー 週次定点観測 | https://claude.ai/artifact/8yev96zRruPECPTdCEu7P8 | 4 | reports/ | レポートの日付 YYYY-MM-DD |

## 手順（<種類>・<URL>・<本数> は上の表から）
1. `python3 /home/claude/semis-data/tools/archive_doc.py <種類> --recent <本数>`
   レポートの場所の新しい<本数>本について、/home/claude/archive_docs/<種類>/ に <id>.meta.json と <id>.body.json を作り、id とファイルの場所の一覧を表示する。
   本文は変えない。どこにも送らない。リポジトリの外に作るので git add -A には入らない。
2. ArtifactData（道具の一覧に無ければ ToolSearch の query: "select:ArtifactData" で読み込む）の query で、ページにすでにある id を読む。
   url は <URL>、collection: "reports"、query: {"order_by": {"field": "as_of", "direction": "desc"}, "limit": 30}。
3. 1 の一覧のうちページに無い id だけを、ArtifactData の batch（url は <URL>）で書く。1本につき2つ：
   {"op": "set", "collection": "reports", "doc_id": "<id>", "file_path": "<meta_file>"} と {"op": "set", "collection": "bodies", "doc_id": "<id>", "file_path": "<body_file>"}。
   今回の分と、過去に入れ損ねた分が一緒に入る。無いものが0本なら何も書かない。新しく作る文書なので if_version は要らない。
   すでにある id を書き直すとき（同じ日付の訂正版、補完の作り直し）だけ、その2つを get して version を読み、if_version を付けて set する。
4. 書けなかったとき（ArtifactData が見つからない場合を含む）は通知を増やさず、最後の返答に「読む用の保管ページに保存できませんでした」と1行書くだけでよい。
   次の回の 3 で自動的に入る。レポートの配信と GitHub への保存は続ける。
   口座・保有・数量はこのページにも書かない（本文に無いので、本文をそのまま入れるかぎり入らない）。

補完した日・週が新しい<本数>本に入らないときは、手順1を `--id <id>` に替えてその1本を作る。
