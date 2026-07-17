# 0007. ランブック検索にRAGを採用

## Context

エージェントが障害対応の方針を判断する際、`runbooks/`配下のMarkdownドキュメント（高CPU・
高メモリ・レイテンシ急増・サービス再起動時の対応手順）を参照できるようにしたい。実装の
選択肢としては、

- ランブックの全文をシステムプロンプトに毎回埋め込む
- ファイル名やキーワードの単純な文字列検索で該当ドキュメントを探す
- ベクトル埋め込みによる意味検索（RAG）で、クエリに関連するチャンクだけを取得する

という案があった。

## Decision

RAG（Retrieval-Augmented Generation）を採用し、`search_runbook`というMCPツールとして公開する。
実装は`mcp_server/tools/rag.py`で、LlamaIndexの`VectorStoreIndex`と永続化されたChromaDBストア
（`chroma_db/`, コレクション`runbooks`）、埋め込みには`sentence-transformers/all-MiniLM-L6-v2`を
使用する。`Settings.llm = None`によりLLMを介さない純粋な検索とし、ヒットしたチャンクの
生テキストをそのままエージェントに返す（要約はしない。判断はエージェント側のLLMに委ねる）。

## Consequences

- ランブックが増えてもシステムプロンプトが肥大化しない。クエリに関連する部分だけを
  都度取得できる
- `llama-index`/`chromadb`/`sentence-transformers`（torch込み）という重い依存関係が増える。
  これを`mcp_server`だけに閉じ込めるため、Dockerイメージを分割している（[ADR-0001](0001-service-split-and-docker-images.md)）
- このリポジトリのランブックは4ファイルと少なく、チャンク数も小さいため、実際のスケール
  上の恩恵より「実務で使われるRAGパターンを実装している」という技術的な実演の意味合いが
  強い。本番相当の規模でどこまで有効かは未検証
