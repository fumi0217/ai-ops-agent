# 0012. chat/engine.pyにpytestを導入する

## Context

これまでこのリポジトリにはテストスイートがなく、動作確認はDocker起動しての手動確認に
頼っていた。ポートフォリオとして、どこかにテストを入れる価値はある。ただし全部を
一律にカバーするのではなく、テストする価値がある箇所を選ぶことにした。

`mock_services`は5サービス分のメトリクス・ログ・アラートを固定シナリオとして
返すだけのモックで、その動きは`state.py`にハードコードされている。ここに
「再起動したらメトリクスが戻る」のようなテストを書いても、自分で決めたシナリオが
その通りに書かれているかを再確認するだけになり、あまり意味がない。

一方`chat/engine.py`の`_agentic_loop`は、Geminiが返したツール呼び出しのうち
どれを即実行し、どれを`restart_service`/`scale_service`のような破壊的操作として
オペレーターの確認待ちにするかを判断する、このリポジトリの中核ロジックの1つ
([ADR-0002](0002-human-in-the-loop-confirmation.md))。同一ターンに複数のツール
呼び出しが混在した場合の処理や、確認後にレスポンスをマージする
`resume_after_confirmation_async`も含め、分岐が複雑でバグが入り込みやすい。
ここはテストで担保する価値がある。

## Decision

`chat/engine.py`を対象にpytestを導入する。

- `requirements-dev.txt`(新規)に`pytest`/`pytest-asyncio`を分離。Dockerイメージ
  (`Dockerfile.light`/`Dockerfile.rag`)には含めず、テスト実行時だけ追加でインストールする
- `pytest.ini`で`asyncio_mode = auto`にし、async関数をそのまま`async def test_...`
  として書けるようにする
- `tests/test_chat_engine.py`: 純粋関数(`describe_error`、JSON Schema→genai Schema変換、
  `is_display_message`)に加えて、`_agentic_loop`本体(通常のツール呼び出しの即時実行、
  破壊的操作の保留、同一ターンに両方が混在した場合の分岐)、`run_conversation_async`/
  `resume_after_confirmation_async`(MCPセッションの初期化・確認後のレスポンスのマージ)
  をカバーする
- `tests/conftest.py`: Gemini API・MCPサーバーへの実接続はせず、`google-genai`/`mcp`
  SDKの実際の型(`genai.types.Part`、`mcp.types.CallToolResult`など)を使ってレスポンスを
  組み立てるヘルパーを用意し、それを`unittest.mock`で差し込む。フィールド名の変更など
  上流の破壊的変更があった場合にテストが落ちるようにするため、手書きの適当なdictではなく
  実際の型を使っている
- `.github/workflows/tests.yml`(新規): `chat/**`・`tests/**`を変更するPRとmainへの
  pushで`pytest`を実行する

## Consequences

- `mock_services`と`frontend`にはテストを追加していない。`mock_services`は上記の理由で
  対象外、`frontend`はスコープをPython側の1ファイルに絞るため今回は見送った
  (`next lint`/`next build`のTypeScriptチェックのみ、これまで通り)
- 全体のカバレッジを追う体制ではないため、今後新しいツールや分岐を`chat/engine.py`に
  足すときにテストを書くかどうかは、その都度「テストする価値があるロジックか」で判断する
