# 0005. 環境変数の管理方針

## Context

`MOCK_SERVICES_URL`/`MCP_SERVER_URL`は当初、`.env`・`docker-compose.yml`の`environment:`・
各サービスの`config.py`のデフォルト値という3箇所に重複して定義されていた。Docker実行時は
`environment:`が`.env`の値を上書きするため、`.env`を編集しても実際には反映されない
（`docker-compose.yml`を見ないと気づけない）という分かりにくさがあった。
また`mock_services`は環境変数を一切読まないにもかかわらず`env_file: .env`を持っており、
`GEMINI_API_KEY`のような機密情報を不要なコンテナにまで渡していた。

## Decision

値の性質によって定義場所を分ける。

- **秘密情報**（`GEMINI_API_KEY`など、オペレーターごとに異なり、必要なサービスにしか
  渡してはいけない値）: `.env`/`.env.example`に置く。必要なサービスにのみ`env_file: .env`で渡す
  （`mock_services`と`mcp_server`は使わないので渡さない）
- **Dockerネットワーク上のURL**（`http://mock_services:8002`のような、compose上のサービス名・
  ポートに依存する値）: `docker-compose.yml`の`environment:`に一本化する。`.env`には重複して
  書かない
- **ローカル開発時のデフォルト値**: 各サービスの`config.py`が`os.getenv("...", "http://localhost:...")`
  という形でフォールバックを持ち、Docker外で個別に起動する場合はこのデフォルトで動く

## Consequences

- ある実行モード（Docker / ローカル）における「その値がどこで決まるか」が1箇所に定まり、
  「.envで設定したのに反映されない」という混乱がなくなる
- Dockerネットワーク上のURLを確認・変更したい場合は`.env`ではなく`docker-compose.yml`を
  見る必要がある
- `mock_services`・`mcp_server`のコンテナに`GEMINI_API_KEY`が渡らなくなり、
  不要な機密情報の伝播を防げる
