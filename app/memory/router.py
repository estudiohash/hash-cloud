from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from authlib.integrations.starlette_client import OAuth
from app.core.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
from app.core.jwt import require_auth, decode_token
from jwt import ExpiredSignatureError, InvalidTokenError
from app.memory.service import check_memory_status, create_user_memory, read_user_memory, write_user_memory

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


@router.get("/authorize")
async def memory_authorize(request: Request, token: str = Query(...)):
    try:
        payload = decode_token(token)
    except HTTPException:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    request.session["pending_user_id"] = payload.get("sub")
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
