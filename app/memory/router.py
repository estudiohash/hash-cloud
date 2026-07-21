from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from authlib.integrations.starlette_client import OAuth
from app.core.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
from app.core.jwt import require_auth
from app.memory.service import check_memory_status, create_user_memory, read_user_memory, write_user_memory, delete_user_document, rename_user_document

router = APIRouter(prefix="/memory", tags=["memory"])

import os
MEMORY_CALLBACK_URI = os.environ.get("MEMORY_CALLBACK_URI", "https://hash-cloud-production.up.railway.app/memory/callback")

oauth = OAuth()
oauth.register(
    name="google_drive",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "https://www.googleapis.com/auth/drive.file",
        "token_endpoint_auth_method": "client_secret_post",
    },
)

MEMORY_ERRORS = {
    "not_found":     (status.HTTP_404_NOT_FOUND,  "Memoria no encontrada"),
    "unauthorized":  (status.HTTP_401_UNAUTHORIZED, "Acceso revocado. El usuario debe reautorizar."),
    "inaccessible":  (status.HTTP_403_FORBIDDEN,   "El documento de memoria no es accesible. Verificá que exista en Google Drive."),
}


def _raise_memory_error(error: str):
    code, detail = MEMORY_ERRORS.get(error, (500, "Error inesperado"))
    raise HTTPException(status_code=code, detail=detail)


class WriteMemoryRequest(BaseModel):
    document: str
    name: str
    description: str
    row: dict


@router.get("/status")
def memory_status(user: dict = Depends(require_auth)):
    result = check_memory_status(user["id"])
    return {"user_id": user["id"], **result}


@router.post("/authorize")
async def memory_authorize(request: Request, user: dict = Depends(require_auth)):
    # El token ya fue validado por require_auth — user["id"] es el sub verificado
    request.session["pending_user_id"] = user["id"]
    return await oauth.google_drive.authorize_redirect(
        request,
        MEMORY_CALLBACK_URI,
        access_type="offline",
        prompt="consent",
    )


@router.get("/callback")
async def memory_callback(request: Request):
    token = await oauth.google_drive.authorize_access_token(request)
    user_id = request.session.get("pending_user_id")

    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sesión inválida")

    refresh_token = token.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Refresh token no recibido")

    create_user_memory(user_id, token["access_token"], refresh_token)
    return RedirectResponse(url="https://hash-ai.vercel.app/")


@router.get("")
def memory_read(user: dict = Depends(require_auth)):
    result = read_user_memory(user["id"])
    if result is None:
        _raise_memory_error("not_found")
    if "error" in result:
        _raise_memory_error(result["error"])
    return result


@router.post("")
def memory_write(body: WriteMemoryRequest, user: dict = Depends(require_auth)):
    try:
        return write_user_memory(user["id"], body.document, body.name, body.description, body.row)
    except ValueError as e:
        _raise_memory_error(str(e))


class RenameMemoryRequest(BaseModel):
    name: str


@router.delete("/{key}")
def memory_delete(key: str, user: dict = Depends(require_auth)):
    try:
        found = delete_user_document(user["id"], key)
    except ValueError as e:
        _raise_memory_error(str(e))
    if not found:
        _raise_memory_error("not_found")
    return {"deleted": True, "key": key}


@router.patch("/{key}/rename")
def memory_rename(key: str, body: RenameMemoryRequest, user: dict = Depends(require_auth)):
    try:
        found = rename_user_document(user["id"], key, body.name)
    except ValueError as e:
        _raise_memory_error(str(e))
    if not found:
        _raise_memory_error("not_found")
    return {"renamed": True, "key": key, "new_name": body.name}


from fastapi import UploadFile, File
from app.memory.service import upload_txt_as_memory


@router.post("/upload-txt")
async def upload_txt(file: UploadFile = File(...), user: dict = Depends(require_auth)):
    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .txt")
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="El archivo debe estar en UTF-8")
    return upload_txt_as_memory(user["id"], file.filename, text)
