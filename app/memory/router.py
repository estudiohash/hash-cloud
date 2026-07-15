from fastapi import APIRouter, Depends, HTTPException, Request, status
from authlib.integrations.starlette_client import OAuth
from app.core.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
from app.core.jwt import require_auth
from app.memory.service import check_memory_status, create_user_memory, read_user_memory

router = APIRouter(prefix="/memory", tags=["memory"])

MEMORY_CALLBACK_URI = "http://localhost:8000/memory/callback"

oauth = OAuth()
oauth.register(
    name="google_sheets",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/drive.file",
        "token_endpoint_auth_method": "client_secret_post",
    },
)


@router.get("/status")
def memory_status(user: dict = Depends(require_auth)):
    result = check_memory_status(user["id"])
    return {"user_id": user["id"], **result}


@router.post("/session")
def memory_session(request: Request, user: dict = Depends(require_auth)):
    request.session["pending_user_id"] = user["id"]
    return {"ok": True}


@router.get("/authorize")
async def memory_authorize(request: Request):
    if not request.session.get("pending_user_id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión no iniciada")
    return await oauth.google_sheets.authorize_redirect(
        request,
        MEMORY_CALLBACK_URI,
        access_type="offline",
        prompt="consent",
    )


@router.get("/callback")
async def memory_callback(request: Request):
    token = await oauth.google_sheets.authorize_access_token(request)
    user_id = request.session.get("pending_user_id")

    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sesión inválida")

    refresh_token = token.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Refresh token no recibido")

    return create_user_memory(user_id, token["access_token"], refresh_token)


@router.get("")
def memory_read(user: dict = Depends(require_auth)):
    memory = read_user_memory(user["id"])
    if memory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memoria no encontrada")
    return memory
