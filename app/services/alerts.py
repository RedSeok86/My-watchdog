import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

ALERTS_PATH = os.path.join("data", "alerts.json")


def _utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_id() -> str:
    # alert_id는 "변경/장애 이벤트" 단위로 유지되게 timestamp 기반으로 생성
    return _utc_ts()


def load_alerts(path: str = ALERTS_PATH) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def save_alerts(alerts: Dict[str, Any], path: str = ALERTS_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _best_summary(status: str, checks: List[Dict[str, Any]]) -> str:
    """
    CRIT이면 CRIT 원인 1개,
    WARN이면 WARN 원인 1개,
    없으면 상태 문자열 반환.
    """
    if not checks:
        return status

    if status == "CRIT":
        for c in checks:
            if c.get("severity") == "CRIT":
                return f'{c.get("name", "check")}: {c.get("message", "")}'.strip()

    if status == "WARN":
        for c in checks:
            if c.get("severity") == "WARN":
                return f'{c.get("name", "check")}: {c.get("message", "")}'.strip()

    return status


def _counts(checks: List[Dict[str, Any]]) -> (int, int, int):
    crit = sum(1 for c in checks if c.get("severity") == "CRIT")
    warn = sum(1 for c in checks if c.get("severity") == "WARN")
    return crit + warn, crit, warn


def upsert_alert(
    alerts: Dict[str, Any],
    server_name: str,
    status: str,
    checks: List[Dict[str, Any]],
    ts: Optional[str] = None,
) -> None:
    """
    핵심 정책:
    - WARN/CRIT 발생 시: alert 생성/갱신 (resolved=False)
    - OK로 회복 시: 절대 삭제(pop)하지 않고 resolved=True만 찍음
    - alert_id는 "이벤트" 단위. (resolved된 이후 새 WARN/CRIT이 오면 새 alert_id 발급)
    """
    now_ts = ts or _utc_ts()
    cur = alerts.get(server_name)

    total, crit_cnt, warn_cnt = _counts(checks)

    if status in ("WARN", "CRIT"):
        summary = _best_summary(status, checks)

        # 기존 알람이 없거나, 기존 알람이 resolved 상태면 -> 새 이벤트(alert_id 새로 발급)
        if (not isinstance(cur, dict)) or cur.get("resolved") is True:
            alerts[server_name] = {
                "alert_id": _now_id(),
                "severity": status,
                "summary": summary,
                "count": total,
                "crit_count": crit_cnt,
                "warn_count": warn_cnt,
                "first_seen_ts": now_ts,
                "last_seen_ts": now_ts,
                "resolved": False,
            }
        else:
            # 진행 중인 알람이면 동일 alert_id 유지하면서 내용 갱신
            cur["severity"] = status
            cur["summary"] = summary
            cur["count"] = total
            cur["crit_count"] = crit_cnt
            cur["warn_count"] = warn_cnt
            cur["last_seen_ts"] = now_ts
            cur["resolved"] = False
            cur.pop("resolved_ts", None)

    else:
        # OK 회복: 삭제 금지. 존재하면 resolved만 표시.
        if isinstance(cur, dict) and cur:
            cur["resolved"] = True
            cur["resolved_ts"] = now_ts
            cur["last_seen_ts"] = now_ts
            # count 정보는 유지(대시보드 요약에 쓰일 수 있음)
            cur.setdefault("count", total)
            cur.setdefault("crit_count", crit_cnt)
            cur.setdefault("warn_count", warn_cnt)