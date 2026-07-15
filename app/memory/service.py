from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from app.memory.repository import get_user_memory, save_user_memory
from app.core.credentials_repository import save_refresh_token

SHEET_NAME = "HASH — Memoria"
INITIAL_HEADERS = [["id", "name", "description", "created_at"]]


def check_memory_status(user_id: str) -> dict:
    entry = get_user_memory(user_id)
    if not entry:
        return {"status": "not_found"}
    return {"status": "registered", "spreadsheet_id": entry["spreadsheet_id"]}


def create_user_memory(user_id: str, access_token: str, refresh_token: str) -> dict:
    creds = Credentials(token=access_token)
    service = build("sheets", "v4", credentials=creds)

    spreadsheet = service.spreadsheets().create(body={
        "properties": {"title": SHEET_NAME},
        "sheets": [{"properties": {"title": "id_name"}}],
    }).execute()

    spreadsheet_id = spreadsheet["spreadsheetId"]

    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="id_name!A1:D1",
        valueInputOption="RAW",
        body={"values": INITIAL_HEADERS},
    ).execute()

    entry = save_user_memory(user_id, spreadsheet_id)
    save_refresh_token(user_id, refresh_token)

    return {"spreadsheet_id": spreadsheet_id, "created_at": entry["created_at"]}


def _rows_to_objects(values: list) -> list:
    if not values or len(values) < 2:
        return []
    headers = values[0]
    return [dict(zip(headers, row)) for row in values[1:]]


def read_user_memory(user_id: str) -> dict:
    from app.core.credentials_repository import get_refresh_token
    from app.memory.repository import get_user_memory
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from app.core.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET

    entry = get_user_memory(user_id)
    if not entry:
        return None

    refresh_token = get_refresh_token(user_id)
    if not refresh_token:
        return None

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
    )
    creds.refresh(Request())

    spreadsheet_id = entry["spreadsheet_id"]
    service = build("sheets", "v4", credentials=creds)

    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheet_titles = [s["properties"]["title"] for s in spreadsheet["sheets"]]

    index = []
    documents = []

    for title in sheet_titles:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{title}!A:Z",
        ).execute()
        values = result.get("values", [])

        if title == "id_name":
            index = _rows_to_objects(values)
        else:
            documents.append({
                "id": title,
                "name": title,
                "rows": _rows_to_objects(values),
            })

    return {
        "id": spreadsheet_id,
        "source": "google_sheets",
        "index": index,
        "documents": documents,
    }
