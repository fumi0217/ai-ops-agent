# 0009. chat APIはステートレス、フロントエンドがRoute Handler経由でプロキシする

## Context

[ADR-0008](0008-streamlit-then-nextjs.md)の計画に沿ってNext.jsへ移行するにあたり、
`chat/engine.py`（Streamlit非依存の純粋関数として既に設計済み）をどうHTTP API化するか、
会話履歴の状態をどこで持つか、ブラウザとPython側のAPIサーバーの間にどういう関係を
持たせるかを決める必要があった。

## Decision

- **サーバー側にセッションを持たない**。`chat/api.py`(FastAPI)は`messages`配列
  （Geminiのraw content形式、[ADR-0004](0004-message-history-format.md)のまま）を
  リクエストボディで受け取り、更新後の配列をレスポンスでそのまま返す。クライアント
  （Next.jsのReact state）が会話履歴の唯一の保持者になる。`chat/engine.py`の
  `run_conversation_async`/`resume_after_confirmation_async`が元々「messagesを受け取って
  返す」という形をしていたため、この設計にそのまま乗せられる。
- **ブラウザは`chat_api`を直接叩かない**。Next.jsのRoute Handler
  (`app/api/chat/route.ts`, `app/api/chat/confirm/route.ts`)がサーバー側で
  `CHAT_API_URL`(内部Dockerネットワーク上の`chat_api`)にプロキシする。ブラウザから見える
  APIは常にNext.js自身(`/api/chat`, `/api/chat/confirm`)だけで、`chat_api`の存在・
  ホスト名を意識しない。
- **ツールの日本語ラベル・警告文は`chat/api.py`側で解決する**。`pending_action`の
  レスポンスに`label`/`warning`/`description`を含めるため、フロントエンドは
  ツール名→表示文言のマッピングを持たない（単一のソースを`chat/api.py`に保つ）。

## Consequences

- サーバー側のセッションストア（Redis等）が不要。実装がシンプルになる一方、
  ブラウザタブをリロードすると会話履歴が失われる（Streamlit版でもタブを閉じれば
  同様に失われていたため、実質的な後退ではないと判断した）
- ブラウザ→`chat_api`間の通信が発生しないため、CORS設定が不要
- `chat/engine.py`は今回の移行で一切変更していない。ADR-0008で意図した設計
  （UIフレームワーク非依存の純粋関数）が実際に機能した
- 1ターンの応答はブロッキング（`POST /chat`が完了するまで待つ）で、Streamlit版の
  `st.status("考えています...")`と同等の体験。SSE等によるトークン単位のストリーミングは
  今回のスコープ外
