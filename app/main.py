from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager
from app.core.config import SESSION_SECRET
from app.core.database import init_db, get_cursor
from app.chat.repository import ensure_tables
from app.auth.router import router as auth_router
from app.context.router import router as context_router
from app.memory.router import router as memory_router
from app.compiler.router import router as compiler_router
from app.chat.router import router as chat_router
from app.payment_monitor import monitor_loop
import asyncio
import logging

log = logging.getLogger(__name__)


def ensure_payment_tables():
    with get_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS hash_cloud (
                key text PRIMARY KEY,
                value text
            )
        """)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ensure_tables()
    ensure_payment_tables()
    task = asyncio.create_task(monitor_loop())
    yield
    task.cancel()


app = FastAPI(title="HASH Cloud", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://hash-ai.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    https_only=True,
    same_site="none",
)

app.include_router(auth_router)
app.include_router(context_router)
app.include_router(memory_router)
app.include_router(compiler_router)
app.include_router(chat_router)


@app.get("/health")
def health():
    return {"status": "ok"}
