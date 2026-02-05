import time
from typing import List, Tuple
import boto3
import os


def get_ssm_client():
    region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2"))
    return boto3.client("ssm", region_name=region)


def run_shell(instance_id: str, commands: List[str], wait_seconds: int = 20) -> Tuple[bool, str]:
    """
    SSM Run Command로 쉘 커맨드 실행 후 stdout/stderr 요약 반환
    """
    ssm = get_ssm_client()
    try:
        resp = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": commands},
            TimeoutSeconds=max(30, wait_seconds),
        )
        cmd_id = resp["Command"]["CommandId"]
    except Exception as e:
        return False, f"send_command FAIL ({e.__class__.__name__})"

    deadline = time.time() + wait_seconds
    last_status = None
    while time.time() < deadline:
        try:
            inv = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=instance_id)
            status = inv.get("Status")
            last_status = status
            if status in ("Success", "Failed", "Cancelled", "TimedOut"):
                stdout = (inv.get("StandardOutputContent") or "").strip()
                stderr = (inv.get("StandardErrorContent") or "").strip()
                if status == "Success":
                    return True, stdout[:2000]
                return False, (stderr or stdout or f"status={status}")[:2000]
        except Exception:
            last_status = "Unknown"
        time.sleep(2)

    return False, f"wait timeout (last_status={last_status})"
