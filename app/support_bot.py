"""
support_bot.py
Bot de Telegram de soporte para HASH AI.
"""
import asyncio
import logging
import os
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from app.core.database import get_cursor

log = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("SUPPORT_BOT_TOKEN")
ADMIN_CHAT_ID = 826400018

CRITICAL_KEYWORDS = [
    "pagué", "pague", "pago", "usdt", "transferí", "transferi",
    "no se activó", "no se activo", "perdí", "perdi", "plata",
    "no funciona", "pro", "activar", "reembolso", "devolución", "devolucion",
]

# Estado de la conversación por usuario
user_states: dict[int, dict] = {}


def ensure_support_tables():
    with get_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                id SERIAL PRIMARY KEY,
                telegram_user_id BIGINT NOT NULL,
                telegram_username TEXT,
                email TEXT,
                message TEXT NOT NULL,
                is_critical BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)


def is_critical(text: str) -> bool:
    return any(kw in text.lower() for kw in CRITICAL_KEYWORDS)


def save_ticket(user_id: int, username: str | None, email: str, message: str, critical: bool):
    try:
        with get_cursor() as cur:
            cur.execute("""
                INSERT INTO support_tickets (telegram_user_id, telegram_username, email, message, is_critical)
                VALUES (%s, %s, %s, %s, %s)
            """, [user_id, username, email, message, critical])
    except Exception as e:
        log.error(f"save_ticket error: {e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name or str(user_id)

    # Inicializar estado
    if user_id not in user_states:
        user_states[user_id] = {
            "state": "waiting_description",
            "description": "",
            "email": "",
        }

    state = user_states[user_id]

    # Manejo de foto
    if update.message.photo:
        if state["state"] == "waiting_screenshot":
            photo = update.message.photo[-1]
            caption = (
                f"🆘 *Nuevo ticket de soporte*\n"
                f"👤 Usuario: @{username} (`{user_id}`)\n"
                f"📧 Email: `{state['email']}`\n"
                f"📝 Problema: {state['description']}"
            )
            await context.bot.send_photo(
                chat_id=ADMIN_CHAT_ID,
                photo=photo.file_id,
                caption=caption,
                parse_mode="Markdown"
            )
            save_ticket(user_id, username, state["email"], state["description"], is_critical(state["description"]))
            user_states[user_id]["state"] = "done"
            await update.message.reply_text(
                "✅ Recibimos tu caso. Nuestro equipo lo va a revisar y te vamos a contactar por email en menos de 24 horas."
            )
        else:
            await update.message.reply_text("Primero contame cuál es tu problema.")
        return

    text = update.message.text or ""
    if not text.strip():
        return

    if state["state"] == "waiting_description":
        state["description"] = text
        state["state"] = "waiting_email"
        await update.message.reply_text("Anotado. ¿Cuál es el email con el que te registraste en HASH?")

    elif state["state"] == "waiting_email":
        state["email"] = text
        state["state"] = "waiting_screenshot"
        await update.message.reply_text("Perfecto. Mandame una captura de pantalla como comprobante.")

    elif state["state"] == "waiting_screenshot":
        await update.message.reply_text("Necesito la captura como imagen, no como texto.")

    elif state["state"] == "done":
        await update.message.reply_text(
            "Tu caso ya fue registrado. Si tenés otro problema escribinos de nuevo."
        )


async def run_bot():
    ensure_support_tables()
    log.info("Support bot iniciado.")
    bot_app = Application.builder().token(TELEGRAM_TOKEN).updater(None).build()
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    bot_app.add_handler(MessageHandler(filters.PHOTO, handle_message))
    await bot_app.initialize()
    await bot_app.start()
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
