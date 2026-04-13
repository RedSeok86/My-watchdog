from flask import Blueprint, render_template, abort
from app.services.storage import (
    get_latest_snapshot,
    get_snapshot,
    list_snapshots,
)
from app.services.inventory import get_servers
from app.services.diff import get_latest_diff_for_server

bp = Blueprint("watchdog", __name__)


@bp.get("/")
def dashboard():
    servers = get_servers()
    snap = get_latest_snapshot()

    # 스냅샷이 없으면 빈 화면
    if not snap:
        return render_template("dashboard.html", servers=servers, snapshot=None, status_map={})

    status_map = {s["name"]: s for s in snap["servers"]}  # name 기준 매핑
    return render_template("dashboard.html", servers=servers, snapshot=snap, status_map=status_map)


@bp.get("/server/<name>")
def server_detail(name: str):
    servers = get_servers()
    if name not in [s["name"] for s in servers]:
        abort(404)

    latest = get_latest_snapshot()
    if not latest:
        return render_template(
            "server_detail.html",
            server_name=name,
            latest=None,
            history=[],
            diff=None,
        )

    # 최신 스냅샷에서 해당 서버만 추출
    latest_server = next((x for x in latest["servers"] if x["name"] == name), None)

    # 최근 스냅샷 몇 개 히스토리
    hist = []
    for sid in list_snapshots(limit=20):
        s = get_snapshot(sid)
        if not s:
            continue
        row = next((x for x in s["servers"] if x["name"] == name), None)
        if row:
            hist.append({"snapshot_id": sid, "ts": s["ts"], "status": row["status"], "checks": row["checks"]})

    diff = get_latest_diff_for_server(name)

    return render_template(
        "server_detail.html",
        server_name=name,
        latest=latest_server,
        history=hist,
        diff=diff,
    )


@bp.get("/mazer-test")
def mazer_test():
    return render_template("mazer_test.html")
