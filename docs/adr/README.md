# Architecture Decision Records (ADR)

このディレクトリには、このリポジトリの設計上の判断とその理由を記録しています。
「なぜこう実装したか」を後から追えるようにするためのもので、実装の詳細（何がどこにあるか）は
`CLAUDE.md`、使い方は`README.md`を参照してください。

## 一覧

| # | タイトル |
|---|---------|
| [0001](0001-service-split-and-docker-images.md) | サービス構成とDockerイメージの分割 |
| [0002](0002-human-in-the-loop-confirmation.md) | 破壊的操作のHuman-in-the-loop確認 |
| [0003](0003-runbook-search-in-process.md) | search_runbookのin-process呼び出し |
| [0004](0004-message-history-format.md) | メッセージ履歴をGemini content形式のまま保持 |
| [0005](0005-env-var-management.md) | 環境変数の管理方針 |
| [0006](0006-mcp-adoption.md) | ツール呼び出しにMCPを採用 |
| [0007](0007-rag-for-runbook-search.md) | ランブック検索にRAGを採用 |
| [0008](0008-streamlit-then-nextjs.md) | UIはまずStreamlit、将来的にNext.jsへ移行 |

## フォーマット

各ADRは以下の構成で記述します。

- **Context**: 何が問題/検討事項だったか
- **Decision**: 何を選んだか
- **Consequences**: その結果どうなったか（トレードオフ含む）

## 関連ドキュメント

- [ASGI / uvicorn / FastAPI・FastMCPの関係](../asgi-and-uvicorn.md) — このリポジトリ固有の意思決定ではなく、
  一般的な技術仕様の整理（ADR-0001と関連）
