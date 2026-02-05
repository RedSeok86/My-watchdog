import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(ROOT, "data")
SNAP_DIR = os.path.join(DATA_DIR, "snapshots")
DIFF_DIR = os.path.join(DATA_DIR, "diffs")


def ensure_dirs():
    os.makedirs(SNAP_DIR, exist_ok=True)
    os.makedirs(DIFF_DIR, exist_ok=True)


def now_id() -> str:
    # 예: 20260204T132455
    return datetime.now().strftime("%Y%m%dT%H%M%S")


def write_snapshot(snapshot: Dict[str, Any]) -> str:
    ensure_dirs()
    sid = snapshot.get("id") or now_id()
    snapshot["id"] = sid
    path = os.path.join(SNAP_DIR, f"{sid}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    return sid


def list_snapshots(limit: int = 50) -> List[str]:
    ensure_dirs()
    files = [x for x in os.listdir(SNAP_DIR) if x.endswith(".json")]
    files.sort(reverse=True)
    ids = [x.replace(".json", "") for x in files]
    return ids[:limit]


def get_snapshot(snapshot_id: str) -> Optional[Dict[str, Any]]:
    ensure_dirs()
    path = os.path.join(SNAP_DIR, f"{snapshot_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_latest_snapshot() -> Optional[Dict[str, Any]]:
    ids = list_snapshots(limit=1)
    if not ids:
        return None
    return get_snapshot(ids[0])


def get_previous_snapshot() -> Optional[Dict[str, Any]]:
    ids = list_snapshots(limit=2)
    if len(ids) < 2:
        return None
    return get_snapshot(ids[1])


def write_diff(diff_obj: Dict[str, Any]) -> str:
    ensure_dirs()
    did = diff_obj.get("id") or now_id()
    diff_obj["id"] = did
    path = os.path.join(DIFF_DIR, f"{did}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(diff_obj, f, ensure_ascii=False, indent=2)
    return did


def list_diffs(limit: int = 50) -> List[str]:
    ensure_dirs()
    files = [x for x in os.listdir(DIFF_DIR) if x.endswith(".json")]
    files.sort(reverse=True)
    ids = [x.replace(".json", "") for x in files]
    return ids[:limit]


def get_diff(diff_id: str) -> Optional[Dict[str, Any]]:
    ensure_dirs()
    path = os.path.join(DIFF_DIR, f"{diff_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
