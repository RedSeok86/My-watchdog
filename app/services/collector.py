import socket
from datetime import datetime
from typing import Any, Dict, List, Tuple
import requests
import hashlib
import textwrap


from app.services.inventory import get_servers
from app.services.ssm_exec import run_shell
from app.services.storage import write_snapshot, get_latest_snapshot, get_previous_snapshot
from app.services.diff import build_and_store_diff


def tcp_check(host: str, port: int, timeout: int = 3) -> Tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"TCP {host}:{port} OK"
    except Exception as e:
        return False, f"TCP {host}:{port} FAIL ({e.__class__.__name__})"


def http_check(url: str, timeout: int = 5) -> Tuple[bool, str]:
    try:
        r = requests.get(url, timeout=timeout)
        if 200 <= r.status_code < 400:
            return True, f"HTTP {url} OK ({r.status_code})"
        return False, f"HTTP {url} FAIL ({r.status_code})"
    except Exception as e:
        return False, f"HTTP {url} FAIL ({e.__class__.__name__})"


def ssm_disk_root_pct(instance_id: str, warn_over: int, crit_over: int, wait_seconds: int = 20) -> Dict[str, Any]:
    ok, out = run_shell(
        instance_id,
        ["df -P / | tail -n 1 | awk '{print $5}' | tr -d '%'"],
        wait_seconds=wait_seconds,
    )
    if not ok:
        return {"name": "SSM disk /", "ok": False, "severity": "CRIT", "message": out}

    try:
        used = int(out.strip().splitlines()[-1])
    except Exception:
        return {"name": "SSM disk /", "ok": False, "severity": "CRIT", "message": f"Parse FAIL: {out}"}

    if used >= crit_over:
        return {"name": "SSM disk /", "ok": False, "severity": "CRIT", "message": f"/ used {used}% >= {crit_over}%"}
    if used >= warn_over:
        return {"name": "SSM disk /", "ok": True, "severity": "WARN", "message": f"/ used {used}% >= {warn_over}%"}
    return {"name": "SSM disk /", "ok": True, "severity": "OK", "message": f"/ used {used}%"}


def ssm_systemd_active(instance_id: str, service: str, wait_seconds: int = 20) -> Dict[str, Any]:
    ok, out = run_shell(instance_id, [f"systemctl is-active {service} || true"], wait_seconds=wait_seconds)
    if not ok:
        return {"name": f"SSM systemd {service}", "ok": False, "severity": "CRIT", "message": out}

    status = out.strip().splitlines()[-1] if out.strip() else "unknown"
    if status == "active":
        return {"name": f"SSM systemd {service}", "ok": True, "severity": "OK", "message": f"{service}: active"}
    return {"name": f"SSM systemd {service}", "ok": False, "severity": "CRIT", "message": f"{service}: {status}"}


def decide_server_status(checks: List[Dict[str, Any]]) -> str:
    # CRIT 하나라도 있으면 CRIT
    if any(c["severity"] == "CRIT" for c in checks):
        return "CRIT"
    # WARN 있으면 WARN
    if any(c["severity"] == "WARN" for c in checks):
        return "WARN"
    return "OK"


def run_collection_once(make_diff: bool = True) -> Dict[str, Any]:
    servers = get_servers()

    snapshot = {
        "id": None,
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "servers": [],
        "summary": {"ok": 0, "warn": 0, "crit": 0},
    }

    for s in servers:
        checks: List[Dict[str, Any]] = []

        ip = s["ip"]
        # TCP
        for port in s.get("tcp_ports", []) or []:
            ok, msg = tcp_check(ip, int(port), timeout=3)
            checks.append({
                "name": f"TCP {port}",
                "ok": ok,
                "severity": "OK" if ok else "CRIT",
                "message": msg,
            })

        # HTTP
        for url in s.get("http_urls", []) or []:
            ok, msg = http_check(url, timeout=5)
            checks.append({
                "name": f"HTTP {url}",
                "ok": ok,
                "severity": "OK" if ok else "CRIT",
                "message": msg,
            })

        # SSM
        ssm_spec = s.get("ssm") or {}
        instance_id = ssm_spec.get("instance_id")
        if instance_id:
            for c in ssm_spec.get("checks", []) or []:
                ctype = c.get("type")
                if ctype == "disk_root_pct":
                    checks.append(ssm_disk_root_pct(
                        instance_id,
                        warn_over=int(c.get("warn_over", 80)),
                        crit_over=int(c.get("crit_over", 90)),
                        wait_seconds=20,
                    ))
                elif ctype == "systemd_active":
                    svc = c.get("service")
                    if svc:
                        checks.append(ssm_systemd_active(instance_id, svc, wait_seconds=20))
                elif ctype == "command_text":
                        checks.append(ssm_command_text(
                            instance_id,
                            name=c.get("name", "command"),
                            cmd=c.get("cmd", "echo missing-cmd"),
                            wait_seconds=int(c.get("wait_seconds", 20)),
                            max_chars=int(c.get("max_chars", 1800)),
                        ))
                elif ctype == "command_hash":
                        checks.append(ssm_command_hash(
                            instance_id,
                            name=c.get("name", "command"),
                            cmd=c.get("cmd", "echo missing-cmd"),
                            wait_seconds=int(c.get("wait_seconds", 20)),
                        ))

                else:
                    checks.append({
                        "name": f"SSM {ctype}",
                        "ok": True,
                        "severity": "WARN",
                        "message": f"Unknown SSM check type: {ctype}",
                    })


        status = decide_server_status(checks)

        snapshot["servers"].append({
            "name": s["name"],
            "ip": ip,
            "status": status,
            "checks": checks,
        })

        if status == "OK":
            snapshot["summary"]["ok"] += 1
        elif status == "WARN":
            snapshot["summary"]["warn"] += 1
        else:
            snapshot["summary"]["crit"] += 1

    sid = write_snapshot(snapshot)
    snapshot["id"] = sid

    if make_diff:
        old = get_previous_snapshot()
        new = get_latest_snapshot()
        if old and new:
            build_and_store_diff(old, new)

    return snapshot

def ssm_command_text(instance_id: str, name: str, cmd: str, wait_seconds: int = 20, max_chars: int = 1800) -> Dict[str, Any]:
    """
    SSM으로 명령 실행 결과(텍스트)를 저장.
    - 너무 길면 잘라서 저장
    - 실패하면 CRIT
    """
    ok, out = run_shell(instance_id, [cmd], wait_seconds=wait_seconds)
    if not ok:
        return {"name": f"CMD {name}", "ok": False, "severity": "CRIT", "message": out}

    out = (out or "").strip()
    if len(out) > max_chars:
        out = out[:max_chars] + "\n...(truncated)"
    return {"name": f"CMD {name}", "ok": True, "severity": "OK", "message": out}


def ssm_command_hash(instance_id: str, name: str, cmd: str, wait_seconds: int = 20) -> Dict[str, Any]:
    """
    SSM으로 명령 실행 결과를 해시로 저장(변경 감지용).
    - 출력은 노출 최소화 (hash + line count)
    - 실패하면 CRIT
    """
    ok, out = run_shell(instance_id, [cmd], wait_seconds=wait_seconds)
    if not ok:
        return {"name": f"HASH {name}", "ok": False, "severity": "CRIT", "message": out}

    out = (out or "").strip()
    h = hashlib.sha256(out.encode("utf-8", errors="ignore")).hexdigest()
    lines = out.count("\n") + (1 if out else 0)
    return {"name": f"HASH {name}", "ok": True, "severity": "OK", "message": f"sha256={h} lines={lines}"}

