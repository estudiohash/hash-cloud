from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status
from authlib.integrations.starlette_client import OAuth
from app.core.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, MEMORY_CALLBACK_URI
from app.core.jwt import require_auth
from app.memory.service import (
    upload_txt_as_memory,
    check_memory_status,
    create_user_memory,
    read_user_memory,
    write_user_memory,
    delete_user_document,
    rename_user_document,
)

router = APIRouter(prefix="/memory", tags=["memory"])

ERROR_MAP = {
    "not_found":     (status.HTTP_404_NOT_FOUND,            "Memoria no encontrada"),
    "unauthorized":  (status.HTTP_401_UNAUTHORIZED,         "Acceso revocado. El usuario debe reautorizar."),
    "quota":         (status.HTTP_429_TOO_MANY_REQUESTS,    "Cuota de API agotada. Intentá más tarde."),
    "not_connected": (status.HTTP_412_PRECONDITION_FAILED,  "El usuario no ha conectado su memoria."),
}

oauth = OAuth()
oauth.register(
    name="google_drive",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile https://www.googleapis.com/auth/drive.file"},
)


def _http_error(key: str):
    code, detail = ERROR_MAP.get(key, (500, "Error interno"))
    raise HTTPException(status_code=code, detail=detail)


@router.get("/status")
def memory_status(user: dict = Depends(require_auth)):
    return check_memory_status(user["id"])


@router.post("/authorize")
async def memory_authorize(request: Request, user: dict = Depends(require_auth)):
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
    user_id = request.session.pop("pending_user_id", None)
    if not user_id:
        raise HTTPException(status_code=400, detail="Sesión inválida")
    access_token = token.get("access_token")
    refresh_token = token.get("refresh_token")
    create_user_memory(user_id, access_token=access_token, refresh_token=refresh_token)
    return {"ok": True}


@router.get("")
def get_memory(user: dict = Depends(require_auth)):
    result = read_user_memory(user["id"])
    if result is None:
        _http_error("not_found")
    return result


@router.post("")
def post_memory(body: dict, user: dict = Depends(require_auth)):
    try:
        return write_user_memory(
            user["id"],
            document=body.get("document", ""),
            name=body.get("name", ""),
            description=body.get("description", ""),
            row=body.get("row", {}),
        )
    except ValueError as e:
        _http_error(str(e))


@router.delete("/{key}")
def delete_memory(key: str, user: dict = Depends(require_auth)):
    try:
        ok = delete_user_document(user["id"], key)
        if not ok:
            _http_error("not_found")
        return {"ok": True}
    except ValueError as e:
        _http_error(str(e))


@router.patch("/{key}/rename")
def rename_memory(key: str, body: dict, user: dict = Depends(require_auth)):
    try:
        ok = rename_user_document(user["id"], key, body.get("name", ""))
        if not ok:
            _http_error("not_found")
        return {"ok": True}
    except ValueError as e:
        _http_error(str(e))


@router.post("/upload-txt")
async def upload_txt(file: UploadFile = File(...), user: dict = Depends(require_auth)):
    """Sube un archivo .txt y lo guarda como documento de memoria del usuario."""
    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .txt")
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="El archivo debe estar en UTF-8")
    result = upload_txt_as_memory(user["id"], file.filename, text)
    return result
