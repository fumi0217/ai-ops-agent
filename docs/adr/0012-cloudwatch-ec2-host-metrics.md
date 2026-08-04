# 0012. read-only の実監視ツールとしてCloudWatch EC2メトリクスを追加

## Context

現状のツールはすべて`mock_services`のインメモリなシミュレーションデータに対する操作で、
実際のAWSリソースには一切触れていない。運用処理をmockでなくす、あるいは監視ツールを
1つ追加する方向性を検討した結果、破壊的操作(再起動・スケール)を実際のリソースに対して
行うようにするのはHuman-in-the-loopの安全設計や「常時稼働のprod環境を持たない」という
このリポジトリの前提と噛み合わないため見送り、**read-onlyな実データソースを1つだけ**
追加する方針にした([ADR-0002](0002-human-in-the-loop-confirmation.md)、
[ADR-0011](0011-github-actions-oidc-cicd.md)と同じ「ポートフォリオ規模に見合った
スコープ」の考え方)。

候補として、EC2ホスト上でDockerソケットをマウントして`docker stats`相当を取る案も
検討したが、コンテナからホストの実質的なroot権限を握れてしまうため見送った。

## Decision

`mcp_server`に`get_ec2_host_metrics`ツールを追加する。他のツールと違い、`mock_services`
を経由せず、boto3でAWS CloudWatch APIを直接呼び、EC2ホスト自身の実CPU使用率
(`AWS/EC2` `CPUUtilization`)を取得する(`mcp_server/tools/aws_metrics.py`)。

認証はEC2インスタンスのIAMロール(`infra/iam.tf`の`aws_iam_role.ec2_cloudwatch_read`
+ `aws_iam_instance_profile`)に委ねる。静的なAWSアクセスキーは使わない
(`GEMINI_API_KEY`同様、コンテナ内に秘密情報を置かない方針を踏襲)。ロールの権限は
`ec2:DescribeInstances`と`cloudwatch:GetMetricStatistics`のみ(いずれもAWS側の制約で
resource-level認可ができないため`Resource: "*"`)で、`ec2:*Manage`系や他のmutatingな
アクションは一切含めない — このロールはコンテナから到達可能なため、read-onlyであることが
重要。

インスタンスの特定には、`ec2:DescribeInstances`を`tag:Name = ai-ops-agent-server`で
フィルタする方式にした(単一インスタンス構成なのでこれで自分自身を一意に特定できる)。

EC2のIMDSはデフォルトで`HttpPutResponseHopLimit = 1`になっており、Dockerコンテナ内から
のアクセスはブリッジネットワーク越しの追加ホップとしてブロックされる。boto3がIAMロールの
一時クレデンシャルを取得する経路もこのIMDS経由のため、ここを許可しないと
`get_ec2_host_metrics`はコンテナ内からAWS認証情報を一切取得できずツールとして機能しない。
そのため`infra/ec2.tf`の`metadata_options`で`http_put_response_hop_limit = 2`(コンテナが
到達するのに必要な1ホップ分だけ)に設定した。`http_tokens = "required"`(IMDSv2必須)は
維持しており、古いIMDSv1のSSRFリスクを再度開けることはない。

`infra/`が初めてIAMリソースを管理することになるため、`infra/bootstrap/iam.tf`の
GitHub Actions用IAMポリシーにも、この特定のロール/instance profile ARNに絞った
IAM管理アクション(`iam:CreateRole`等)と、`iam:PassedToService = ec2.amazonaws.com`
条件付きの`iam:PassRole`を追加した(旧来の「IAMリソースを管理していないので`iam:*`は
一切付与しない」というコメントは、この変更に合わせて更新した)。この`infra/bootstrap/`
の変更は、[ADR-0010](0010-terraform-state-bootstrap-split.md)の運用ルール通り、
リポジトリ所有者が自分のAWS認証情報で手動apply して初めてCIが対応する`infra/`の
変更を適用できるようになる。

## Consequences

- `mock_services`の5サービスに対するメトリクスはすべてシミュレーションのままだが、
  ホストインスタンス自体のCPU使用率だけは実際のAWS環境から取得できるようになり、
  「全部mock」というポートフォリオの弱点を最小限のスコープで補える
- `mcp_server`はEC2上で動かした場合のみこのツールが正しく動作する(ローカルDocker
  Composeやこのリポジトリの開発用サンドボックスなど、AWS認証情報もEC2メタデータも
  ない環境では`NoCredentialsError`または対象インスタンス無しのエラーになる — これは
  他のツール同様、例外を握りつぶさずFastMCPの`isError`として自然に伝播させる)
- `infra/`が初めてIAMリソースを管理するようになったため、`infra/bootstrap/`のCIロールに
  スコープ済みの`iam:PassRole`を含む新しい権限を追加する必要があり、
  ユーザーが手動で`infra/bootstrap/`を再applyしない限りCIはこの`infra/`の変更を
  適用できない
- **既知の限界**: `get_metrics(metric_type='cpu')`(mockのシミュレーション値)と
  `get_ec2_host_metrics`(実際のCloudWatch値)は、どちらも「CPU」という同じ概念に対して
  別々の値を返す。5サービスの障害シナリオはmock側の数値にしか仕込まれていないため、
  「サーバーの状況を見て」のような曖昧な指示でエージェントがホスト側の実CPUを返すと、
  シナリオ上のCPU値と矛盾して見える可能性がある。今回は「read-onlyな実データソースを
  1つ追加できることを示す」までをスコープとし、この意味的な競合の解消(例:
  シミュレーション側に対応概念のない指標 — `StatusCheckFailed`など — への差し替え)は
  今回は行わず、将来の検討事項として残す
