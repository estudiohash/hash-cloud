from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from app.core.config import SESSION_SECRET
from app.auth.router import router as auth_router
from app.context.router import router as context_router

app = FastAPI(title="HASH Cloud")

app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

app.include_router(auth_router)
app.include_router(context_router)


@app.get("/health")
def health():
    return {"status": "ok"}
