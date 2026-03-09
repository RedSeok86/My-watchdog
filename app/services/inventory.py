from typing import List, Dict, Any
import json
import os
from pathlib import Path


def get_inventory_path() -> Path:
    path_str = os.getenv("WATCHDOG_INVENTORY_PATH", "inventory.json")
    return Path(path_str)


def get_servers() -> List[Dict[str, Any]]:
    path = get_inventory_path()

    if not path.exists():
        raise FileNotFoundError(
            f"Inventory file not found: {path}. "
            f"Create inventory.json or set WATCHDOG_INVENTORY_PATH correctly."
        )

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("inventory.json must contain a JSON list.")

    return data