"""
support_bot.py
Bot de Telegram de soporte para HASH AI.
- Responde automáticamente con IA (Gemini)
- Detecta casos críticos (pago perdido, sin activación)
- Guarda toda la conversación en DB para revisión
"""
import asyncio
import logging
import os
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from app.core.database import get_cursor

log = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("SUPPORT_BOT_TOKEN")

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
    return any(kw in text.lower() for kw in CRITICAL_KEYWORDS)


def save_ticket(user_id: int, username: str | None, message: str, response: str, critical: bool):
    try:
        with get_cursor() as cur:
            cur.execute("""
                INSERT INTO support_tickets (telegram_user_id, telegram_username, message, response, is_critical)
                VALUES (%s, %s, %s, %s, %s)
            """, [user_id, username, message, response, critical])
    except Exception as e:
        log.error(f"save_ticket error: {e}")


def get_ai_response(user_message: str, conversation_history: list) -> str:
    try:
        from app.llm.gemini import GeminiProvider
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history + [{"role": "user", "content": user_message}]
        gemini = GeminiProvider()
        return gemini.generate(messages)
    except Exception as e:
        log.error(f"get_ai_response error: {e}")
    return "Gracias por escribir. Tu mensaje fue registrado y lo vamos a revisar pronto."


conversation_histories: dict[int, list] = {}


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text or ""
    if not text.strip():
        return

    user_id = user.id
    username = user.username or user.first_name or str(user_id)

    if user_id not in conversation_histories:
        conversation_histories[user_id] = []
    history = conversation_histories[user_id]

    critical = is_critical(text)

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, get_ai_response, text, history)

    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": response})
    if len(history) > 20:
        conversation_histories[user_id] = history[-20:]

    save_ticket(user_id, username, text, response, critical)

    if critical:
        response += "\n\n⚠️ *Tu caso fue marcado como prioritario.*"

    await update.message.reply_text(response, parse_mode="Markdown")


async def run_bot():
    ensure_support_tables()
    log.info("Support bot iniciado.")
    bot_app = Application.builder().token(TELEGRAM_TOKEN).updater(None).build()
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await bot_app.initialize()
    await bot_app.start()
    # Polling manual compatible con el event loop de FastAPI
    offset = None
    while True:
        try:
            updates = await bot_app.bot.get_updates(offset=offset, timeout=10, allowed_updates=["message"])
            for update in updates:
                offset = update.update_id + 1
                await bot_app.process_update(update)
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error(f"run_bot polling error: {e}")
            await asyncio.sleep(5)
    await bot_app.stop()
    await bot_app.shutdown()
