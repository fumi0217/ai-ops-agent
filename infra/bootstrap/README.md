# infra/bootstrap/

`infra/`(VPC/EC2/ECR)がS3リモートバックエンドとGitHub ActionsのOIDC federationを使うための、
前提となるリソースをここで作る: state用のS3バケットと、GitHub Actions用のOIDCプロバイダ+IAM role。

`infra/`自身はこのS3バケットにstateを置くので、`infra/`をCIから`terraform apply`できるように
なる前に、このバケットとIAM roleが**先に**存在している必要がある。CIはまだ存在しないIAM roleを
assumeできないので、この一度きりのブートストラップだけは、あなた自身の実際のAWS認証情報を使って
**ローカルから手動で**apply する。以降、CIがこの環境を触ることは一切ない。

## 適用手順(一度だけ)

このリポジトリの他の場所と同様、terraformは以下のようにDocker経由で実行する想定:

```bash
cd infra/bootstrap
docker run -it --rm \
  -v "$(pwd):/opt" \
  -v ~/.aws:/root/.aws:ro \
  -e AWS_PROFILE=default \
  -w /opt \
  --entrypoint ash \
  hashicorp/terraform:latest
```

コンテナ内で:

```sh
terraform init
terraform plan
terraform apply
```

`~/.aws`をマウントする代わりに、`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_SESSION_TOKEN`を
`docker run -e`で渡しても構わない。いずれにせよ、ここで使うのは**あなた自身の**AWS認証情報で、
GitHub Secretsに入れるものとは別。

## apply後にやること

`terraform output`で出た4つの値を、それぞれ以下に反映する:

| output | 反映先 |
|---|---|
| `state_bucket_name` | `infra/main.tf`の`backend "s3" { bucket = "..." }` |
| `state_bucket_region` | `infra/main.tf`の`backend "s3" { region = "..." }` |
| `github_actions_role_arn` | GitHub repo Settings → Secrets and variables → Actions → Variables → `AWS_ROLE_ARN` |
| `oidc_provider_arn` | 反映先なし(参考情報。`infra/`側からは参照しない) |

その後、`infra/`側で:

```sh
cd infra
terraform init -reconfigure   # ローカルstateからS3バックエンドへ移行
```

## 注意

- このディレクトリのstateは意図的にローカル管理のまま(`infra/`用のバケットを自分自身が
  作るという構造上、リモートバックエンドに置けない)。`terraform.tfstate`はマシン上に残るので、
  紛失した場合は同じ内容で作り直す必要がある(頻繁に触らないリソースなので許容している)。
- ここにあるIAM roleのpolicyは、現時点の`infra/`(VPC/EC2/セキュリティグループ/ECR)が
  必要とする権限だけを持つ。`infra/`に新しい種類のリソース(IAMロール等)を追加する場合は、
  このpolicyも合わせて更新が必要。
