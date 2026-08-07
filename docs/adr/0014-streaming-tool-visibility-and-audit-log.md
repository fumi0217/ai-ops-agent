# 0014. MCPツール呼び出しのリアルタイム可視化と、破壊的操作の監査ログ

## Context

エージェントが複数ターンかけて調査している間、`POST /chat`が完了するまでUIには
「考えています...」としか出ず、実際にどのMCPツールを呼んでいるかが見えなかった。
またこれまで、破壊的操作(`restart_service`/`scale_service`)は確認カードで承認を
求めているが、「いつ・何が・どういう理由で実行されたか」を後から追える記録が
残らなかった。

この2点をあわせて実装した。

## Decision

**リアルタイム可視化はストリーミングレスポンス(SSE)で実装した。** ポーリング方式
(フロントが定期的に「今何してる?」を聞きに行く)も検討したが、それには「今どの
リクエストの状態か」を紐づけるサーバー側セッションが要る。このリポジトリは
[ADR-0009](0009-stateless-chat-api.md)で意図的にサーバー側セッションを持たない設計
にしているので、それを崩さずに済むストリーミングの方が既存アーキテクチャに合う。
WebSocketも検討したが、双方向通信は不要(1リクエストにつき1方向にイベントが流れる
だけ)なので、そこまでの仕組みは不要と判断した。

`POST /chat` / `POST /chat/confirm`を`text/event-stream`のレスポンスに変更し、
`tool_call`(ツール呼び出し開始/終了)・`final`(今までのJSONレスポンス相当)・
`error`イベントを順に流す。`chat/engine.py`の`_call_mcp_tool`に`on_tool_call`
コールバックを追加し、実際にMCPツールを呼ぶ直前・直後に呼ぶことで、読み取り系・
破壊的操作問わずすべてのツール呼び出しがイベントとして拾える。

- **トレードオフ**: ストリーミングを開始した時点でHTTPステータスは200固定になる
  ため、今までの「異常時は502を返す」(`chat/api.py`の`HTTPException`)という方式が
  使えなくなった。エラーもストリーム内の`error`イベントとして表現するように変更した。

**監査ログは`chat/engine.py`側(新規`chat/audit.py`)に記録する。** 実行の理由
(`reason`)は`mcp_server/tools/operations.py`の`restart_service`/`scale_service`
関数の引数にしか現れず、`mock_services`にはそもそも転送されていない。「実行された」
という事実と「なぜ」を両方知っているのは、確認後に実際にツールを呼ぶ
`chat/engine.py`の`resume_after_confirmation_async`だけなので、`mock_services`側の
変更はせず、ここで記録することにした。

- 対象は`MUTATING_TOOLS`(`restart_service`/`scale_service`)のみ。読み取り系
  (メトリクス・ログ・ランブック参照)は機密情報を扱わないため対象外というのは
  明確な判断。
- `mock_services/state.py`同様、インメモリ(`chat_api`再起動でリセット)。実運用の
  ツールを想定しているわけではないポートフォリオなので、永続化までは不要と判断した。
- 承認待ちがキャンセルされた場合は記録しない(実行されていないため)。
- ユーザー/操作者の識別情報は記録しない
  ([ADR-0013](0013-no-app-level-auth.md)通り、認証なし・単一操作者前提のため)。

## Consequences

- `chat/api.py`のエラーハンドリングがHTTPステータスベースからin-streamイベント
  ベースに変わった。フロントエンド(`app/api/chat/route.ts`等)も、chat_apiが
  ストリームを開始する前に失敗した場合(リクエストバリデーションエラーなど)は
  引き続きJSONエラーとして、ストリーム開始後の失敗は`error`イベントとして扱う
  両対応にしている。
- 監査ログ・ツール呼び出しイベントの表示ラベルはどちらも`chat/api.py`の
  `_TOOL_LABELS`で解決してから返す。フロントエンドはツール名→表示名のマッピングを
  持たない、という既存の方針([`_build_pending_action`](../../chat/api.py)と同じ)
  を維持している。
- `chat/api.py`(SSE配線そのもの)は、[ADR-0012](0012-pytest-for-chat-engine.md)の
  スコープ方針(`chat/api.py`は対象外)を踏襲し、自動テストは追加していない。
  `chat/engine.py`側の`on_tool_call`呼び出しと監査ログ記録はpytestでカバーしている。
- 監査ログ閲覧用の`app/audit/page.tsx`はNext.jsのServer Componentとして実装し、
  `chat_api`を直接fetchしている。`app/page.tsx`(クライアントコンポーネントのため
  `CHAT_API_URL`に直接アクセスできず、Route Handler経由が必要)とは異なり、この
  ページはインタラクティブな状態を持たないため、専用のRoute Handlerを新設せずに
  済んでいる。
