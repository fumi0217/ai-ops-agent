"""MCP tool for real AWS CloudWatch metrics about the EC2 host.

Unlike the other tools in this package, this one doesn't proxy to
mock_services — it calls AWS directly via boto3, using the EC2 instance's
IAM role (see infra/iam.tf) rather than static credentials.
"""

from datetime import datetime, timedelta, timezone

import boto3

from mcp_server.config import AWS_REGION, EC2_INSTANCE_NAME_TAG


def _find_instance_id() -> str:
    ec2 = boto3.client("ec2", region_name=AWS_REGION)
    resp = ec2.describe_instances(
        Filters=[
            {"Name": "tag:Name", "Values": [EC2_INSTANCE_NAME_TAG]},
            {"Name": "instance-state-name", "Values": ["running"]},
        ]
    )
    for reservation in resp["Reservations"]:
        for instance in reservation["Instances"]:
            return instance["InstanceId"]
    raise RuntimeError(f"No running EC2 instance found with tag Name={EC2_INSTANCE_NAME_TAG!r}")


def get_ec2_host_metrics(minutes: int = 15) -> dict:
    """
    Get real CPU utilization for the EC2 instance hosting this app, sourced
    from AWS CloudWatch — distinct from the simulated per-service metrics
    the other tools return.

    Args:
        minutes: How many minutes of history to look back over (1-1440).
    """
    instance_id = _find_instance_id()
    cloudwatch = boto3.client("cloudwatch", region_name=AWS_REGION)
    now = datetime.now(timezone.utc)
    resp = cloudwatch.get_metric_statistics(
        Namespace="AWS/EC2",
        MetricName="CPUUtilization",
        Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
        StartTime=now - timedelta(minutes=minutes),
        EndTime=now,
        Period=60,
        Statistics=["Average"],
        Unit="Percent",
    )
    datapoints = sorted(resp["Datapoints"], key=lambda d: d["Timestamp"])
    return {
        "instance_id": instance_id,
        "metric": "CPUUtilization",
        "unit": "Percent",
        "datapoints": [{"timestamp": d["Timestamp"].isoformat(), "average": d["Average"]} for d in datapoints],
    }
