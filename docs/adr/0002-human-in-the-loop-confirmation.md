# 0002. 破壊的操作のHuman-in-the-loop確認

## Context

エージェントは`restart_service`/`scale_service`という、実際にサービスの状態を変える
（このリポジトリではモックだが、本番を模した）ツールを呼び出せる。LLMの判断だけで
これらを即座に実行してしまうと、意図しない/説明不足な操作が起こり得る。

## Decision

`chat/engine.py`に`MUTATING_TOOLS = {"restart_service", "scale_service"}`という集合を定義し、
エージェンティックループ(`_agentic_loop`)がこの集合に含まれるツール呼び出しを検知した時点で
実行せずに`pending_action`としてUIに差し戻す。ツール自体（`mcp_server`側）には確認の仕組みを
持たせず、確認の強制はMCPサーバーではなく`chat`側だけで行う。`mcp_server`のツールdocstringに
「必ず確認を得てから呼ぶこと」と書いているのはLLMへの指示であり、実際の強制力は
`chat/engine.py`のガードが担っている。

オペレーターが確認カード（`chat/app.py`）で承認した場合のみ、
`resume_after_confirmation_async`が実際にMCPツールを呼び出す。

## Consequences

- LLMの判断がどうであれ、破壊的操作は必ずUIでの明示的な承認を経由する
- 新しい破壊的ツールを追加する際は、`chat/engine.py`の`MUTATING_TOOLS`と
  `chat/app.py`の`_TOOL_LABELS`/`_TOOL_WARNINGS`を手動で同期させる必要がある
  （`CLAUDE.md`の「Adding a new tool」に記載）
- MCPサーバー自体は「確認済みかどうか」を知らない・関知しない設計になっており、
  確認の実体はあくまで`chat`というクライアント側の実装に閉じている
