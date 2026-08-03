# 0010. Terraform stateのS3化とbootstrap rootの分離

## Context

`infra/`(VPC/EC2/セキュリティグループ)のstateはこれまでローカル管理だった。
GitHub Actionsから`terraform apply`を実行するには、stateをリモート(S3)に置く必要がある。

ただし、そのS3バケット自体を`infra/`が管理するstateの中で作ろうとすると、「`infra/`が
リモートバックエンドとして使うバケットを、`infra/`自身がまだ存在しない状態でどう作るか」
という鶏卵問題になる。CIがGitHub Actions用のIAM roleをassumeして`terraform apply`する
ためには、そのIAM role自体も先に存在している必要があり、これも同じ構造の問題を持つ。

## Decision

`infra/bootstrap/`という別のTerraform root(ローカルstate)を新設し、ここに
「`infra/`が動くための前提」だけをまとめる: state用S3バケットと、GitHub Actions用の
OIDC IAM role([ADR-0011](0011-github-actions-oidc-cicd.md)参照)。この root は
CIからは一切触らず、リポジトリ所有者が自分自身のAWS認証情報で最初に一度だけ手動
apply する([infra/bootstrap/README.md](../../infra/bootstrap/README.md)に手順を記載)。

state の排他制御には、DynamoDBロックテーブルではなくTerraform 1.10+のS3
ネイティブロック(`backend "s3" { use_lockfile = true }`)を使う。このプロジェクトは
単一オペレーターで同時apply の心配がなく、DynamoDBテーブルを追加してもIAM権限の
管理対象が増えるだけでメリットが薄いため。

`infra/`本体は`bootstrap`のapply後に出力される`state_bucket_name`/
`state_bucket_region`を`main.tf`のbackendブロックに手で反映し、
`terraform init -reconfigure`でローカルstateからS3へ移行する。

## Consequences

- `infra/bootstrap/`自身のstateはローカルのまま残る。紛失した場合は同じ内容で
  作り直す必要があるが、ほとんど触らないリソース(バケット+IAM role)なので許容している
- `backend`ブロックは変数を参照できない仕様上、バケット名は`main.tf`に文字列として
  手で書く必要がある(bootstrap実行のたびに自動反映されるわけではない)
- DynamoDBロックテーブルを使わない分、複数人が同時に`terraform apply`する運用には
  向かない(このプロジェクトの規模では問題にならない)
