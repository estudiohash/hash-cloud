import json
from pathlib import Path
from datetime import datetime, timezone
from app.core.encryption import encrypt, decrypt

CREDENTIALS_PATH = Path(__file__).parent / "credentials.json"


def _load() -> dict:
    if not CREDENTIALS_PATH.exists():
        return {"users": {}}
    with open(CREDENTIALS_PATH, "r") as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(CREDENTIALS_PATH, "w") as f:
        json.dump(data, f, indent=2)


def get_refresh_token(user_id: str) -> str | None:
    data = _load()
    entry = data["users"].get(user_id)
    if not entry:
        return None
    return decrypt(entry["refresh_token"])


def save_refresh_token(user_id: str, refresh_token: str) -> None:
    data = _load()
    data["users"][user_id] = {
        "refresh_token": encrypt(refresh_token),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _save(data)
