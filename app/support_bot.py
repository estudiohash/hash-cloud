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

SYSTEM_PROMPT = """Sos el bot de soporte de HASH AI, una plataforma de inteligencia artificial.
Respondé de forma breve, directa y amable en español rioplatense.
No tenés acceso a los datos del usuario ni sabés quién es.
Si el usuario menciona cualquier problema, seguí este flujo exacto:
1. Primero pedile que describa bien el problema si no lo hizo.
2. Luego pedile su email de registro en HASH.
3. Luego pedile una captura de pantalla como comprobante.
4. Una vez que tenés email y captura, confirmale que el caso fue registrado y será revisado en menos de 24 horas.
Nunca saltees pasos. Nunca inventes datos del usuario."""


# Estado de la conversación por usuario
# Estados: "waiting_description", "waiting_email", "waiting_screenshot", "done"
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


def get_ai_response(user_message: str, conversation_history: list) -> str:
    try:
        from app.llm.gemini import GeminiProvider
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history + [{"role": "user", "content": user_message}]
        gemini = GeminiProvider()
        return gemini.generate(messages)
    except Exception as e:
        log.error(f"get_ai_response error: {e}")
    return "Gracias por escribir. Tu caso fue registrado y lo revisamos pronto."


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
            "history": [],
        }

    state = user_states[user_id]

    # Manejo de foto
    if update.message.photo:
        if state["state"] == "waiting_screenshot":
            # Reenviar al admin con resumen
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
                "✅ Listo, recibimos tu caso. Lo revisamos en menos de 24 horas."
            )
        else:
            await update.message.reply_text("Primero contame cuál es tu problema.")
        return

    text = update.message.text or ""
    if not text.strip():
        return

    # Flujo por estado
    if state["state"] == "waiting_description":
        state["description"] = text
        state["history"].append({"role": "user", "content": text})
        state["state"] = "waiting_email"
        reply = "Anotado. ¿Cuál es el email con el que te registraste en HASH?"

    elif state["state"] == "waiting_email":
        state["email"] = text
        state["history"].append({"role": "user", "content": text})
        state["state"] = "waiting_screenshot"
        reply = "Perfecto. Ahora mandame una captura de pantalla como comprobante."

    elif state["state"] == "waiting_screenshot":
        reply = "Necesito la captura de pantalla. Mandala como imagen."

    elif state["state"] == "done":
        # Conversación libre post-ticket con IA
        state["history"].append({"role": "user", "content": text})
        loop = asyncio.get_event_loop()
        reply = await loop.run_in_executor(None, get_ai_response, text, state["history"])
        state["history"].append({"role": "assistant", "content": reply})

    else:
        reply = "Contame cuál es tu problema."

    await update.message.reply_text(reply)


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
