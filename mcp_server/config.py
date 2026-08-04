"""MCP Server configuration loaded from environment."""

import os
from dotenv import load_dotenv

load_dotenv()

MOCK_SERVICES_URL = os.getenv("MOCK_SERVICES_URL", "http://localhost:8002")

# Used by get_ec2_host_metrics to self-identify the EC2 instance via
# ec2:DescribeInstances (see infra/ec2.tf's `Name` tag and infra/iam.tf).
EC2_INSTANCE_NAME_TAG = os.getenv("EC2_INSTANCE_NAME_TAG", "ai-ops-agent-server")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-3")
