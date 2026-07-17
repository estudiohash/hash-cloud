import json
import io
import uuid
from datetime import datetime, timezone
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from app.memory.repository import get_user_memory, save_user_memory
from app.core.credentials_repository import save_refresh_token, get_refresh_token

MEMORY_FILENAME = "hash_memory.json"
HASH_FOLDER_NAME = "HASH"

# Estructura base del archivo de memoria
EMPTY_MEMORY = {
    "version": "1.0",
    "index": [],       # lista de { id, name, description, created_at }
    "documents": {}    # dict de { document_id: { name, description, created_at, rows: [] } }
}


# ─────────────────────────────────────────────
# Credenciales
# ─────────────────────────────────────────────

def _get_credentials(user_id: str) -> Credentials | None:
    from app.core.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
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
    return creds


# ─────────────────────────────────────────────
# Drive helpers — un read, un write
# ─────────────────────────────────────────────

def _read_memory_file(drive, file_id: str) -> dict:
    """Descarga el JSON de memoria en un solo request."""
    request = drive.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    buffer.seek(0)
    return json.loads(buffer.read().decode("utf-8"))


def _write_memory_file(drive, file_id: str, memory: dict) -> None:
    """Sube el JSON de memoria en un solo request."""
    content = json.dumps(memory, ensure_ascii=False, indent=2).encode("utf-8")
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype="application/json", resumable=False)
    drive.files().update(fileId=file_id, media_body=media).execute()


def _get_or_create_hash_folder(drive) -> str:
    """Obtiene (o crea) la carpeta HASH en el Drive del usuario."""
    results = drive.files().list(
        q=f"name='{HASH_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id)",
        pageSize=1,
    ).execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]

    folder = drive.files().create(
        body={"name": HASH_FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"},
        fields="id",
    ).execute()
    return folder["id"]


# ─────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────

def check_memory_status(user_id: str) -> dict:
    entry = get_user_memory(user_id)
    if not entry:
        return {"status": "not_found"}

    try:
        creds = _get_credentials(user_id)
    except RefreshError:
        return {"status": "unauthorized"}

    if not creds:
        return {"status": "unauthorized"}

    try:
        drive = build("drive", "v3", credentials=creds)
        drive.files().get(fileId=entry["file_id"], fields="id").execute()
        return {"status": "active", "file_id": entry["file_id"]}
    except HttpError:
        return {"status": "inaccessible", "file_id": entry["file_id"]}


def create_user_memory(user_id: str, access_token: str, refresh_token: str) -> dict:
    creds = Credentials(token=access_token)
    drive = build("drive", "v3", credentials=creds)

    folder_id = _get_or_create_hash_folder(drive)

    content = json.dumps(EMPTY_MEMORY, ensure_ascii=False, indent=2).encode("utf-8")
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype="application/json", resumable=False)

    file_meta = {
        "name": MEMORY_FILENAME,
        "parents": [folder_id],
        "mimeType": "application/json",
    }
    created = drive.files().create(body=file_meta, media_body=media, fields="id").execute()
    file_id = created["id"]

    entry = save_user_memory(user_id, file_id)
    save_refresh_token(user_id, refresh_token)

    return {"file_id": file_id, "created_at": entry["created_at"]}


def read_user_memory(user_id: str) -> dict | None:
    entry = get_user_memory(user_id)
    if not entry:
        return None

    try:
        creds = _get_credentials(user_id)
    except RefreshError:
        return {"error": "unauthorized"}

    if not creds:
        return {"error": "unauthorized"}

    try:
        drive = build("drive", "v3", credentials=creds)
        memory = _read_memory_file(drive, entry["file_id"])
    except HttpError:
        return {"error": "inaccessible"}

    return {
        "id": entry["file_id"],
        "source": "google_drive_json",
        "index": memory.get("index", []),
        "documents": list(memory.get("documents", {}).values()),
    }


def write_user_memory(user_id: str, document: str, name: str, description: str, row: dict) -> dict:
    entry = get_user_memory(user_id)
    if not entry:
        raise ValueError("not_found")

    try:
        creds = _get_credentials(user_id)
    except RefreshError:
        raise ValueError("unauthorized")

    if not creds:
        raise ValueError("unauthorized")

    try:
        drive = build("drive", "v3", credentials=creds)
        memory = _read_memory_file(drive, entry["file_id"])
    except HttpError:
        raise ValueError("inaccessible")

    documents = memory.setdefault("documents", {})
    index = memory.setdefault("index", [])

    document_created = False
    if document not in documents:
        doc_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        documents[document] = {
            "id": doc_id,
            "name": name,
            "description": description,
            "created_at": created_at,
            "rows": [],
        }
        index.append({"id": doc_id, "name": name, "description": description, "created_at": created_at})
        document_created = True

    row_with_ts = {**row, "created_at": datetime.now(timezone.utc).isoformat()}
    documents[document]["rows"].append(row_with_ts)

    _write_memory_file(drive, entry["file_id"], memory)

    return {"document": document, "created": document_created, "row": row_with_ts}
