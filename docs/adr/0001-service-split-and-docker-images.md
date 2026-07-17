# 0001. サービス構成とDockerイメージの分割

## Context

このリポジトリは`mock_services`（モックの運用対象バックエンド）、`mcp_server`（MCPツールサーバー）、
`chat`（Streamlit UI + エージェントループ）の3サービスで構成される。このうち`mcp_server`だけが
ランブック検索(RAG)のために`llama-index`/`chromadb`/`sentence-transformers`（torch込み）という
重い依存関係を必要とし、`mock_services`と`chat`はFastAPI/Streamlit/httpx程度の軽量な依存関係で済む。

## Decision

Dockerイメージを依存関係の重さで2つに分割する。

- `Dockerfile.light`: `mock_services`と`chat`が使う（`requirements-light.txt`のみインストール）
- `Dockerfile.rag`: `mcp_server`が使う（`requirements-rag.txt`のみインストール）

`docker-compose.yml`では3サービスがそれぞれ`build.dockerfile`でどちらかを指定する形にし、
1つのDockerfileに全依存関係をまとめて全サービスで使い回す、という構成は取らない。

## Consequences

- `mock_services`/`chat`のビルドはtorch等を含まず軽量・高速になる
- RAG関連の重い依存関係は`mcp_server`のイメージにのみ閉じ込められる
- 依存関係ファイルが2つに分かれるため、共有すべきパッケージ（例: `httpx`）のバージョンを
  変更する際は両方のrequirementsファイルを意識する必要がある

`mcp_server`の起動コマンドが`uvicorn ... --factory`という形になっている理由（FastMCPのASGIアプリ生成）は
[docs/asgi-and-uvicorn.md](../asgi-and-uvicorn.md)を参照。
