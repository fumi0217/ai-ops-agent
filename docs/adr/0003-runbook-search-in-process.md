# 0003. search_runbookのin-process呼び出し

## Context

`list_services`/`get_metrics`/`get_health`/`get_logs`/`get_alerts`/`restart_service`/`scale_service`は
いずれも`mock_services`が保持する運用データ・状態を操作対象とするため、HTTP経由で`mock_services`を
呼び出す構成になっている。一方`search_runbook`は`runbooks/`をベクトル化したChromaDBストアに対する
検索であり、`mock_services`の状態とは無関係。

## Decision

`search_runbook`のためだけに`mock_services`側へエンドポイントを追加してHTTP経由で呼ぶ構成にはせず、
`mcp_server/tools/runbook.py`から`mcp_server/tools/rag.py`を直接importして呼び出す
（`mcp_server`プロセス内で完結させる）。

## Consequences

- 実データを持たない`mock_services`に「ランブック検索用エンドポイント」という見せかけのAPIを
  追加せずに済む。ネットワークホップも1つ減る
- 一方で、他のツールは全てHTTP経由、`search_runbook`だけがin-process importという
  非対称な実装になる。これは見落としではなく意図的な判断であることをここに明記する
