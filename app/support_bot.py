"""
support_bot.py
Bot de Telegram de soporte para HASH AI.
- Responde automáticamente con IA (Claude/Gemini via HASH Cloud)
- Detecta casos críticos (pago perdido, sin activación)
- Guarda toda la conversación en DB para revisión
"""
import asyncio
import logging
import httpx
import os
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from app.core.database import get_cursor
from app.core.config import DATABASE_URL

log = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("SUPPORT_BOT_TOKEN")
HASH_CLOUD_URL = os.getenv("HASH_CLOUD_URL", "https://hash-cloud-production.up.railway.app")

# Palabras clave que marcan un ticket como crítico
CRITICAL_KEYWORDS = [
    "pagué", "pague", "pago", "usdt", "transferí", "transferi",
    "no se activó", "no se activo", "perdí", "perdi", "plata",
    "no funciona", "pro", "activar", "reembolso", "devolución", "devolucion",
]

SYSTEM_PROMPT = """Sos el bot de soporte de HASH AI, una plataforma de inteligencia artificial.
Respondé de forma breve, directa y amable en español rioplatense.
Si el usuario menciona un pago o problema con su plan pro, decile que su caso fue registrado y será revisado en menos de 24 horas.
Si el problema es técnico, intentá resolverlo vos. Si no podés, decile que fue escalado.
Nunca prometás tiempos menores a 24 horas para problemas de pago.
Nunca digas que sos un bot de IA genérico; sos el soporte oficial de HASH."""


def ensure_support_tables():
    with get_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                id SERIAL PRIMARY KEY,
                telegram_user_id BIGINT NOT NULL,
                telegram_username TEXT,
                message TEXT NOT NULL,
                response TEXT,
                is_critical BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)


def is_critical(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in CRITICAL_KEYWORDS)


def save_ticket(user_id: int, username: str | None, message: str, response: str, critical: bool):
    try:
        with get_cursor() as cur:
            cur.execute("""
                INSERT INTO support_tickets (telegram_user_id, telegram_username, message, response, is_critical)
                VALUES (%s, %s, %s, %s, %s)
            """, [user_id, username, message, response, critical])
    except Exception as e:
        log.error(f"save_ticket error: {e}")


async def get_ai_response(user_message: str, conversation_history: list) -> str:
    """Llama a la API de Anthropic para generar una respuesta de soporte."""
    try:
        messages = conversation_history + [{"role": "user", "content": user_message}]
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": os.getenv("ANTHROPIC_API_KEY", ""),
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 300,
                    "system": SYSTEM_PROMPT,
                    "messages": messages,
                }
            )
            if res.status_code == 200:
                data = res.json()
                return data["content"][0]["text"]
    except Exception as e:
        log.error(f"get_ai_response error: {e}")
    return "Gracias por escribir. Tu mensaje fue registrado y lo vamos a revisar pronto."


# Historial en memoria por sesión (se limpia al reiniciar)
conversation_histories: dict[int, list] = {}


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text or ""

    if not text.strip():
        return

    user_id = user.id
    username = user.username or user.first_name or str(user_id)

    # Mantener historial de la conversación (últimos 10 turnos)
    if user_id not in conversation_histories:
        conversation_histories[user_id] = []

    history = conversation_histories[user_id]

    # Detectar si es crítico
    critical = is_critical(text)

    # Obtener respuesta de IA
    response = await get_ai_response(text, history)

    # Actualizar historial
    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": response})
    # Mantener solo últimos 10 turnos
    if len(history) > 20:
        conversation_histories[user_id] = history[-20:]

    # Guardar en DB
    save_ticket(user_id, username, text, response, critical)

    # Si es crítico, agregar aviso al final
    if critical:
        response += "\n\n⚠️ *Tu caso fue marcado como prioritario.*"

    await update.message.reply_text(response, parse_mode="Markdown")


async def run_bot():
    ensure_support_tables()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    log.info("Support bot iniciado.")
    await app.run_polling(allowed_updates=["message"])
