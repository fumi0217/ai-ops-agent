# 0006. ツール呼び出しにMCP (Model Context Protocol) を採用

## Context

エージェントは`list_services`/`get_metrics`/`restart_service`など、運用操作をLLMにツールとして
呼び出させる必要がある。実装の選択肢としては、

- `chat`プロセス内に直接ツール関数を定義し、Gemini SDKの`FunctionDeclaration`に合わせて実装する
- `mock_services`へのHTTP呼び出しを`chat`から直接行う（ツールサーバーを独立させない）
- ツールをMCPサーバーとして切り出し、`chat`はMCPクライアントとしてツールを利用する

という案があった。

## Decision

MCP (Model Context Protocol) を採用し、運用ツール群を独立した`mcp_server`として公開する。
`chat/engine.py`はMCPクライアント(`ClientSession`)としてツールスキーマを取得し、
`_json_schema_to_genai`でGeminiの`FunctionDeclaration`形式に変換した上でエージェンティック
ループに渡す。

MCPを選んだ理由は、LLM/エージェントとツールの間の呼び出し方法を特定のLLMベンダーの
関数呼び出し仕様に直接結合させず、標準化されたプロトコルの上に構築するため。ツール実装
（`mcp_server`）はGeminiに限らず、MCP対応の別のクライアント（他のLLM、他のUI）からも
再利用できる構成になる。

## Consequences

- ツールを`chat`から独立したプロセス(`mcp_server`)として動かす分、プロセス境界・
  ネットワークホップが1つ増える(`chat` → `mcp_server` → `mock_services`)
- MCPのJSON Schemaベースのツール定義を、都度Geminiの`FunctionDeclaration`形式に変換する
  レイヤー（`_json_schema_to_genai`, `_mcp_tool_to_genai`）が必要になる
- ツール実装がGemini固有のSDKに直接依存しないため、将来LLMプロバイダーを変更したり、
  他のMCP対応クライアントからこのツール群を再利用したりする際の変更コストが小さい
