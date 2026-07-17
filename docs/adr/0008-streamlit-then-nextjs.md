# 0008. UIはまずStreamlit、将来的にNext.jsへ移行

## Context

ポートフォリオ用の個人開発プロジェクトとして、まずエージェントのループ・MCP連携・
human-in-the-loop確認フローといったコア機能を素早く動く形にしたい。フロントエンドに
別言語・別ビルドツールチェーン（Node.js/React等）を持ち込むと、その分セットアップと
状態管理の設計コストが増える。

## Decision

MVP段階のUIはStreamlitを採用する。Pythonで完結させることで`chat/engine.py`（エージェント
ループ）とUIコードを同一プロセス・同一言語で素早く実装できる。

ただし将来的にNext.jsへ移行する計画があるため、`chat/engine.py`はStreamlit固有のAPI
（`st.session_state`等）に依存させず、メッセージ履歴のリストを受け取って更新後の履歴を
返す、という純粋な関数群として設計している。Streamlit依存のコードは`chat/app.py`側に
閉じ込める。

## Consequences

- 単一言語（Python）でエージェントロジックとUIを素早く実装できる
- StreamlitのUIは実務の運用ツールというよりデモ/プロトタイプ然とした見た目になる。
  実務想定の見た目にするためNext.jsへの移行を計画している
- Streamlitの再実行（rerun）駆動モデルに起因する設計（[ADR-0004](0004-message-history-format.md)の
  メッセージ履歴の持ち方など）は、Next.js移行時に見直しが必要になる
- `chat/engine.py`が呼び出し可能な純粋関数として設計されているため、移行時は`chat/app.py`
  を置き換え、Next.jsからは`chat/engine.py`を薄いHTTP/WebSocket API越しに呼び出す構成に
  差し替えることを想定している（未着手）
