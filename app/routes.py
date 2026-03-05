from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime, timedelta
from flask import Blueprint, render_template, abort, redirect, url_for, request, Response

from app.services.storage import (
    get_latest_snapshot,
    get_snapshot,
    list_snapshots,
)
from app.services.inventory import get_servers
from app.services.diff import get_latest_diff_for_server

bp = Blueprint("watchdog", __name__)

ACKS_PATH = "data/acks.json"
ALERTS_PATH = "data/alerts.json"


# -----------------------------
# JSON helpers
# -----------------------------
def load_json(path: str, default):
    """Load JSON file. Return default if file doesn't exist or is invalid."""
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path: str, obj) -> None:
    """Atomic JSON write (safe write). Creates parent dir if missing."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# -----------------------------
# Time / history helpers
# -----------------------------
def _parse_ts(ts: str) -> datetime | None:
    """
    snapshot.ts 문자열을 datetime으로 파싱.
    예: '2026-02-24 13:52:43'
    """
    if not ts:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    return None


def _get_range_hours(range_key: str) -> int:
    return {
        "24h": 24,
        "7d": 24 * 7,
        "30d": 24 * 30,
    }.get(range_key, 24 * 7)  # 기본 7일


def _build_server_history(server_name: str, limit: int = 5000) -> list[dict]:
    """
    전체 스냅샷에서 특정 서버 히스토리를 수집.
    반환: 오래된 -> 최신 순 정렬
    """
    hist = []

    # list_snapshots가 최신->과거 순이라고 가정하고, 마지막에 정렬
    for sid in list_snapshots(limit=limit):
        s = get_snapshot(sid)
        if not s:
            continue

        row = next((x for x in s.get("servers", []) if x.get("name") == server_name), None)
        if not row:
            continue

        ts = s.get("ts")
        dt = _parse_ts(ts)

        hist.append(
            {
                "snapshot_id": sid,
                "ts": ts,
                "dt": dt,
                "status": row.get("status"),
                "checks": row.get("checks", []),
            }
        )

    hist.sort(key=lambda x: (x["dt"] or datetime.min))
    return hist


def _filter_history_by_range(hist: list[dict], range_key: str) -> list[dict]:
    if not hist:
        return []

    hours = _get_range_hours(range_key)
    now = datetime.now()
    cutoff = now - timedelta(hours=hours)

    return [h for h in hist if h.get("dt") and h["dt"] >= cutoff]


def _status_to_num(status: str) -> int:
    # 그래프용 점수 (위로 갈수록 심각)
    mapping = {
        "OK": 0,
        "WARN": 1,
        "CRIT": 2,
    }
    return mapping.get(status or "", -1)


def _build_status_timeline_points(hist: list[dict]) -> list[dict]:
    """
    Chart.js용 타임라인 포인트
    """
    points = []
    for h in hist:
        if not h.get("dt"):
            continue
        points.append(
            {
                "x": h["dt"].strftime("%Y-%m-%d %H:%M:%S"),
                "y": _status_to_num(h.get("status")),
                "status": h.get("status"),
                "snapshot_id": h.get("snapshot_id"),
            }
        )
    return points


def _build_up_down_events(hist: list[dict]) -> list[dict]:
    """
    상태 변화를 기준으로 UP/DOWN 이벤트 생성
    - DOWN: 이전 OK -> 현재 WARN/CRIT
    - UP  : 이전 WARN/CRIT -> 현재 OK
    그 외 상태변화는 CHANGE 로 표기
    """
    events = []
    if not hist:
        return events

    prev = None
    for cur in hist:
        if not prev:
            prev = cur
            continue

        prev_st = prev.get("status")
        cur_st = cur.get("status")

        if prev_st == cur_st:
            prev = cur
            continue

        event_type = "CHANGE"
        if prev_st == "OK" and cur_st in ("WARN", "CRIT"):
            event_type = "DOWN"
        elif prev_st in ("WARN", "CRIT") and cur_st == "OK":
            event_type = "UP"

        events.append(
            {
                "ts": cur.get("ts"),
                "type": event_type,
                "from_status": prev_st,
                "to_status": cur_st,
                "snapshot_id": cur.get("snapshot_id"),
            }
        )
        prev = cur

    # 최신 이벤트가 위로 오도록 역순
    events.reverse()
    return events


def _history_rows_for_csv_by_date(server_name: str, target_date_str: str) -> list[dict]:
    """
    target_date_str: 'YYYY-MM-DD'
    해당 날짜의 서버 히스토리를 CSV용 rows로 반환
    """
    hist = _build_server_history(server_name, limit=10000)

    rows = []
    for h in hist:
        ts = h.get("ts", "")
        if not ts.startswith(target_date_str):
            continue

        checks = h.get("checks", [])
        ok_count = sum(1 for c in checks if c.get("ok") is True)
        no_count = sum(1 for c in checks if c.get("ok") is False)

        rows.append(
            {
                "ts": ts,
                "snapshot_id": h.get("snapshot_id"),
                "status": h.get("status"),
                "checks_total": len(checks),
                "checks_ok": ok_count,
                "checks_no": no_count,
            }
        )

    rows.sort(key=lambda x: x["ts"])
    return rows
# -----------------------------
# Process history helpers (7d chart / csv)
# -----------------------------
PROCESS_CHOICES = [
    ("apache", "Apache"),
    ("uvicorn", "Uvicorn"),
    ("postgresql", "PostgreSQL"),
    ("mariadb", "MariaDB"),
]

# 체크 이름(alias) 후보들 - 실제 수집 체크명에 맞춰 계속 보강 가능
PROCESS_CHECK_ALIASES = {
    "apache": ["apache", "apache2", "httpd"],
    "uvicorn": ["uvicorn"],
    "postgresql": ["postgresql", "postgres", "postgresql.service"],
    "mariadb": ["mariadb", "mysql", "mysqld", "mariadb.service"],
}


def _normalize_text(v: str) -> str:
    return (v or "").strip().lower()


def _match_process_check(check: dict, process_key: str) -> bool:
    """
    latest.checks / history.checks 항목에서 특정 프로세스 체크인지 판별
    - check["name"], check["message"]를 모두 참고
    """
    aliases = PROCESS_CHECK_ALIASES.get(process_key, [])
    name = _normalize_text(check.get("name", ""))
    msg = _normalize_text(check.get("message", ""))

    for a in aliases:
        if a in name or a in msg:
            return True
    return False


def _extract_process_state_from_checks(checks: list[dict], process_key: str):
    """
    반환:
      {
        "up": 1|0|None,   # None이면 해당 스냅샷에 체크 없음
        "ok": bool|None,
        "severity": str|None,
        "name": str|None,
        "message": str|None,
      }
    """
    for c in checks or []:
        if _match_process_check(c, process_key):
            ok = c.get("ok")
            up = 1 if ok is True else 0 if ok is False else None
            return {
                "up": up,
                "ok": ok,
                "severity": c.get("severity"),
                "name": c.get("name"),
                "message": c.get("message"),
            }

    return {
        "up": None,
        "ok": None,
        "severity": None,
        "name": None,
        "message": None,
    }


def _build_process_timeline_points(hist: list[dict], process_key: str) -> list[dict]:
    """
    Chart.js용 포인트 (7d 기준 hist 넣어서 사용)
    y: 1 (UP), 0 (DOWN)
    """
    points = []
    for h in hist:
        dt = h.get("dt")
        if not dt:
            continue

        state = _extract_process_state_from_checks(h.get("checks", []), process_key)
        if state["up"] is None:
            continue

        points.append(
            {
                "x": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "y": state["up"],
                "ts": h.get("ts"),
                "status": "UP" if state["up"] == 1 else "DOWN",
                "severity": state.get("severity"),
                "snapshot_id": h.get("snapshot_id"),
                "check_name": state.get("name"),
                "message": state.get("message"),
            }
        )
    return points


def _build_process_events(hist: list[dict], process_key: str) -> list[dict]:
    """
    UP/DOWN 전환 이벤트만 추출
    """
    events = []
    prev = None

    for h in hist:
        dt = h.get("dt")
        if not dt:
            continue

        state = _extract_process_state_from_checks(h.get("checks", []), process_key)
        if state["up"] is None:
            continue

        cur = {
            "ts": h.get("ts"),
            "snapshot_id": h.get("snapshot_id"),
            "up": state["up"],
            "status": "UP" if state["up"] == 1 else "DOWN",
            "severity": state.get("severity"),
            "check_name": state.get("name"),
            "message": state.get("message"),
        }

        if prev is None:
            prev = cur
            continue

        if prev["up"] != cur["up"]:
            events.append(
                {
                    "ts": cur["ts"],
                    "type": "UP" if cur["up"] == 1 else "DOWN",
                    "from": "UP" if prev["up"] == 1 else "DOWN",
                    "to": cur["status"],
                    "snapshot_id": cur["snapshot_id"],
                    "severity": cur.get("severity"),
                    "check_name": cur.get("check_name"),
                    "message": cur.get("message"),
                }
            )

        prev = cur

    events.reverse()  # 최신 위
    return events


def _build_process_csv_rows_7d(server_name: str, process_key: str) -> list[dict]:
    """
    최근 7일 프로세스 상태 CSV용 rows
    """
    full_hist = _build_server_history(server_name, limit=10000)
    hist_7d = _filter_history_by_range(full_hist, "7d")

    rows = []
    for h in hist_7d:
        state = _extract_process_state_from_checks(h.get("checks", []), process_key)
        if state["up"] is None:
            continue

        rows.append(
            {
                "server_name": server_name,
                "process_key": process_key,
                "ts": h.get("ts"),
                "snapshot_id": h.get("snapshot_id"),
                "up": state["up"],
                "status": "UP" if state["up"] == 1 else "DOWN",
                "severity": state.get("severity") or "",
                "check_name": state.get("name") or "",
                "message": state.get("message") or "",
            }
        )
    return rows

# -----------------------------
# Routes
# -----------------------------
@bp.get("/")
def dashboard():
    servers = get_servers()
    snap = get_latest_snapshot()

    alerts = load_json(ALERTS_PATH, {})
    acks = load_json(ACKS_PATH, {})

    if not snap:
        return render_template(
            "dashboard.html",
            servers=servers,
            snapshot=None,
            status_map={},
            alerts=alerts,
            acks=acks,
        )

    status_map = {s["name"]: s for s in snap.get("servers", [])}

    return render_template(
        "dashboard.html",
        servers=servers,
        snapshot=snap,
        status_map=status_map,
        alerts=alerts,
        acks=acks,
    )


@bp.get("/server/<name>")
def server_detail(name: str):
    servers = get_servers()
    if name not in [s["name"] for s in servers]:
        abort(404)

    range_key = request.args.get("range", "7d")  # 기본 7일
    if range_key not in ("24h", "7d", "30d"):
        range_key = "7d"

    # 프로세스 선택 (기본 apache)
    process_key = request.args.get("process", "apache").lower()
    valid_process_keys = [k for k, _ in PROCESS_CHOICES]
    if process_key not in valid_process_keys:
        process_key = "apache"

    latest = get_latest_snapshot()
    latest_server = None
    if latest:
        latest_server = next((x for x in latest.get("servers", []) if x.get("name") == name), None)

    # 전체 히스토리 수집 -> 기간 필터
    full_hist = _build_server_history(name, limit=10000)
    hist = _filter_history_by_range(full_hist, range_key)

    # 기존 diff는 유지 (최신 diff)
    diff = get_latest_diff_for_server(name)

    # 이벤트 / 그래프 데이터 생성
    events = _build_up_down_events(hist)
    timeline_points = _build_status_timeline_points(hist)

    process_timeline_points = _build_process_timeline_points(hist, process_key)
    process_events = _build_process_events(hist, process_key)


    # 전일 CSV 기본 날짜
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    return render_template(
        "server_detail.html",
        server_name=name,
        latest=latest_server,
        history=hist[-20:][::-1],   # 화면 표시용: 최신 20개 (최신 먼저)
        history_range=range_key,
        diff=diff,
        events=events[:100],        # 최신 100개 이벤트
        timeline_points=timeline_points,
        csv_default_date=yesterday,
        process_choices=PROCESS_CHOICES,
        selected_process=process_key,
        process_timeline_points=process_timeline_points,
        process_events=process_events[:100],
    )


@bp.get("/server/<name>/history.csv")
def server_history_csv(name: str):
    servers = get_servers()
    if name not in [s["name"] for s in servers]:
        abort(404)

    # 기본: 전일
    date_str = request.args.get("date")
    if not date_str:
        date_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # 간단 검증
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return Response("invalid date format. use YYYY-MM-DD", status=400, mimetype="text/plain")

    rows = _history_rows_for_csv_by_date(name, date_str)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["server_name", "date", "ts", "snapshot_id", "status", "checks_total", "checks_ok", "checks_no"])
    for r in rows:
        writer.writerow(
            [
                name,
                date_str,
                r["ts"],
                r["snapshot_id"],
                r["status"],
                r["checks_total"],
                r["checks_ok"],
                r["checks_no"],
            ]
        )

    csv_data = output.getvalue()
    output.close()

    filename = f"{name}_history_{date_str}.csv"
    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


@bp.get("/server/<name>/process-history.csv")
def server_process_history_csv(name: str):
    servers = get_servers()
    if name not in [s["name"] for s in servers]:
        abort(404)

    process_key = request.args.get("process", "apache").lower()
    valid_process_keys = [k for k, _ in PROCESS_CHOICES]
    if process_key not in valid_process_keys:
        return Response("invalid process. use apache|uvicorn|postgresql|mariadb", status=400, mimetype="text/plain")

    rows = _build_process_csv_rows_7d(name, process_key)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "server_name",
        "process_key",
        "ts",
        "snapshot_id",
        "up",
        "status",
        "severity",
        "check_name",
        "message",
    ])

    for r in rows:
        writer.writerow([
            r["server_name"],
            r["process_key"],
            r["ts"],
            r["snapshot_id"],
            r["up"],
            r["status"],
            r["severity"],
            r["check_name"],
            r["message"],
        ])

    csv_data = output.getvalue()
    output.close()

    filename = f"{name}_{process_key}_process_history_7d.csv"
    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@bp.post("/ack/<server_name>")
def ack_server(server_name: str):
    """
    서버별 최신 알림(alerts.json)의 alert_id를
    acks.json에 ack_alert_id로 저장해서 '확인 처리'함.
    """
    alerts = load_json(ALERTS_PATH, {})
    acks = load_json(ACKS_PATH, {})

    alert = alerts.get(server_name)
    if alert:
        acks.setdefault(server_name, {})
        acks[server_name]["ack_alert_id"] = alert.get("alert_id")
        save_json(ACKS_PATH, acks)

    next_url = request.form.get("next")
    if next_url:
        return redirect(next_url)

    return redirect(url_for("watchdog.dashboard"))