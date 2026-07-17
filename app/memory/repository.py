import json
from pathlib import Path
from datetime import datetime, timezone

INDEX_PATH = Path(__file__).parent / "memory_index.json"


def _load() -> dict:
    if not INDEX_PATH.exists():
        return {"users": {}}
    with open(INDEX_PATH, "r") as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(INDEX_PATH, "w") as f:
        json.dump(data, f, indent=2)


def get_user_memory(user_id: str) -> dict | None:
    data = _load()
    return data["users"].get(user_id)


def save_user_memory(user_id: str, file_id: str) -> dict:
    data = _load()
    entry = {
        "file_id": file_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    data["users"][user_id] = entry
    _save(data)
    return entry
