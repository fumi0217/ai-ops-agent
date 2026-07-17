# 0004. メッセージ履歴をGemini content形式のまま保持

## Context

`chat/app.py`はStreamlitの再実行（rerun）モデルの上で動くため、会話履歴を
`st.session_state`に保持する必要がある。この履歴はGemini APIへの`contents`引数として
そのまま渡すものでもある。

## Decision

アプリ独自のチャットスキーマ（例: `{"role": ..., "content": ..., "tool_calls": [...]}`のような
自前の型）を定義してGemini形式との相互変換を行うのではなく、Geminiの生のcontent形式
（`{"role": "user"|"model", "parts": [{"text": ...} | {"function_call": {...}} | {"function_response": {...}}]}`）
を`st.session_state.messages`にそのまま保持し、`chat/app.py`と`chat/engine.py`の両方が
この形をそのまま読み書きする。

表示に関しては、`chat/engine.py`の`is_display_message`が「`text`キーを持つpartがあるかどうか」
だけを見て判定する。`function_call`/`function_response`というキー自体は見ておらず、textを
持たないpartは種類を問わず履歴上は保持しつつUI表示からは除外される。

## Consequences

- 独自スキーマとGemini形式の間の変換レイヤーを持たずに済む
- 一方で、永続化する履歴のフォーマットがGemini SDKの形にそのまま依存するため、
  別のLLMプロバイダに切り替える場合は履歴フォーマットごと見直しが必要になる
- 表示可否の判定（`is_display_message`）は`text`キーの有無だけを見ており、
  `function_call`/`function_response`の中身を直接解釈しているわけではない
