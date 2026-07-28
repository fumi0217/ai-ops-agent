# 0011. GitHub ActionsのCI/CDにOIDC federationを採用

## Context

GitHub Actionsから`infra/`への`terraform apply`と、Dockerイメージのビルド・ECRへの
pushを自動化したい。どちらもAWSへの認証が必要になる。

## Decision

長期のAWSアクセスキーをGitHub Secretsに置く方式ではなく、GitHub ActionsのOIDC
federationを使う。GitHub側のOIDCプロバイダーをAWS IAMに登録し(`infra/bootstrap/iam.tf`)、
ワークフロー実行のたびに短命なトークンでIAM roleをassumeする(`aws-actions/configure-aws-credentials`
の`role-to-assume`)。静的なアクセスキーはリポジトリのどこにも存在しない。

IAM roleは1つに集約し、`terraform.yml`(`infra/`のplan/apply)と`docker-build.yml`
(Dockerイメージのビルド&push)の両方から使う。信頼ポリシーの`sub`条件は、このリポジトリの
`push:main`と`pull_request`の2コンテキストのみに絞る(`pull_request`が必要なのは、
`terraform.yml`のPRジョブが実際のAWS環境に対して`terraform plan`を実行し差分を見るため。
`docker-build.yml`のPRジョブはビルドのみでこのroleを一切assumeしない)。単一リポジトリ・
単一環境のポートフォリオ規模でrole を2つに分ける実益がないため、権限の絞り込みは
IAM policy側(EC2/ECR/S3の具体的なアクションのみ、`iam:*`は一切含まない)で行う。

ECRリポジトリは`docker-compose.yml`が実際にビルドする3イメージ(`Dockerfile.light`/
`Dockerfile.rag`/`frontend/Dockerfile`)にそれぞれ1つずつ、計3つ作る。
`mock_services`と`chat_api`は同じ`Dockerfile.light`のイメージを`command`だけ変えて
使っているため([ADR-0001](0001-service-split-and-docker-images.md))、
サービス数(4)ではなくイメージ数(3)に合わせている。

`docker-build.yml`はPRでは各Dockerfileのビルドのみ(push無し、AWS認証情報も要求しない)、
mainへのpush時のみビルド+ECR pushを行う。`terraform.yml`も同様にPRでは`terraform plan`
のみ(結果は`$GITHUB_STEP_SUMMARY`に出力。PRコメントにはしない — そのために
`pull-requests: write`権限を追加で持たせずに済むため)、main pushで`apply`する。

**EC2上のdocker-composeを新しいイメージで更新する部分は、今回のスコープに含めない。**
CIの責務は「ECRにイメージがpushされるところまで」とし、実機への反映は当面手動とする。

## Consequences

- 静的なAWSアクセスキーがリポジトリ・GitHub Secretsのどこにも存在しない
- IAM roleを1つに集約したことで、信頼ポリシー/policyの管理箇所は少ないが、
  2つのワークフローの権限を分離できていない(現状のリスクの小ささでは許容範囲)
- ECRリポジトリ名(`ai-ops-agent-{light,rag,frontend}`)は`infra/ecr.tf`・
  `docker-build.yml`・`infra/bootstrap/iam.tf`のIAMポリシーのARNの3箇所に
  文字列として重複している。イメージ名を変える場合は3箇所すべての更新が必要
- ECRにイメージをpushした後、実際にEC2上で新しいイメージが動くようにする部分
  (pull&再起動の自動化)は別タスクとして残る
