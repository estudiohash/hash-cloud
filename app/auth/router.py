import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from app.core.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
from app.core.jwt import create_token, require_auth

router = APIRouter(prefix="/auth", tags=["auth"])

# Códigos de un solo uso: {code: {token, expires_at}}
# TTL de 60 segundos; se eliminan al canjearse o al expirar
_pending_codes: dict[str, dict] = {}

oauth = OAuth()
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@router.get("/login")
async def login(request: Request):
    return await oauth.google.authorize_redirect(request, GOOGLE_REDIRECT_URI)


@router.get("/callback")
async def callback(request: Request):
    token = await oauth.google.authorize_access_token(request)
    user = token.get("userinfo")
    jwt_token = create_token(
        id=user.get("sub"),
        name=user.get("name"),
        email=user.get("email"),
    )

    # Generar código de un solo uso (el JWT nunca viaja en la URL)
    code = secrets.token_urlsafe(32)
    _pending_codes[code] = {
        "token": jwt_token,
        "expires_at": datetime.utcnow() + timedelta(seconds=60),
    }

    return RedirectResponse(
        url=f"https://hash-ai.vercel.app/?code={code}",
        status_code=302,
    )


@router.post("/token")
async def exchange_code(body: dict):
    """Canjea un código de un solo uso por el JWT. El código expira en 60 segundos."""
    code = body.get("code", "")

    # Limpiar códigos expirados de paso
    now = datetime.utcnow()
    expired = [k for k, v in _pending_codes.items() if now > v["expires_at"]]
    for k in expired:
        del _pending_codes[k]

    entry = _pending_codes.pop(code, None)
    if not entry or now > entry["expires_at"]:
        raise HTTPException(status_code=401, detail="Código inválido o expirado")

    return {"token": entry["token"]}


@router.get("/me")
def me(user: dict = Depends(require_auth)):
    return user

