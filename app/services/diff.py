from typing import Any, Dict, List, Optional
from app.services.storage import write_diff, list_diffs, get_diff


def _index_checks(server_obj: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {c["name"]: c for c in server_obj.get("checks", [])}


def build_and_store_diff(old_snap: Dict[str, Any], new_snap: Dict[str, Any]) -> str:
    """
    old_snap vs new_snap 비교해서 변경사항만 저장
    """
    old_map = {s["name"]: s for s in old_snap.get("servers", [])}
    new_map = {s["name"]: s for s in new_snap.get("servers", [])}

    server_diffs: List[Dict[str, Any]] = []

    for name, new_srv in new_map.items():
        old_srv = old_map.get(name)
        if not old_srv:
            server_diffs.append({"server": name, "changes": [{"check": "__server__", "old": "N/A", "new": "ADDED"}]})
            continue

        changes = []
        old_checks = _index_checks(old_srv)
        new_checks = _index_checks(new_srv)

        # 체크 이름 기준으로 비교
        for chk_name, new_chk in new_checks.items():
            old_chk = old_checks.get(chk_name)
            if not old_chk:
                changes.append({"check": chk_name, "old": "N/A", "new": f"{new_chk['severity']} | {new_chk['message']}"})
                continue

            old_repr = f"{old_chk['severity']} | {old_chk['message']}"
            new_repr = f"{new_chk['severity']} | {new_chk['message']}"
            if old_repr != new_repr:
                changes.append({"check": chk_name, "old": old_repr, "new": new_repr})

        # old에는 있는데 new에는 없는 체크
        for chk_name in old_checks.keys():
            if chk_name not in new_checks:
                old_chk = old_checks[chk_name]
                changes.append({"check": chk_name, "old": f"{old_chk['severity']} | {old_chk['message']}", "new": "REMOVED"})

        if changes:
            server_diffs.append({"server": name, "changes": changes})

    diff_obj = {
        "id": None,
        "old_id": old_snap["id"],
        "new_id": new_snap["id"],
        "old_ts": old_snap["ts"],
        "new_ts": new_snap["ts"],
        "servers": server_diffs,
    }

    return write_diff(diff_obj)


def get_latest_diff_for_server(server_name: str) -> Optional[Dict[str, Any]]:
    """
    최신 diff들 중에서 server_name 변경사항이 있는 가장 최근 1개 반환
    템플릿에서 쓰기 쉽게 flatten 해서 반환
    """
    for did in list_diffs(limit=50):
        d = get_diff(did)
        if not d:
            continue
        for s in d.get("servers", []):
            if s.get("server") == server_name:
                return {
                    "id": did,
                    "old_ts": d.get("old_ts"),
                    "new_ts": d.get("new_ts"),
                    "changes": s.get("changes", []),
                }
    return None
