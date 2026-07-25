import os
import requests
import logging

log = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{EMBEDDING_MODEL}:embedContent"


def get_embedding(text: str) -> list[float] | None:
    """Genera un embedding de 768 dimensiones para el texto dado."""
    if not GEMINI_API_KEY:
        log.error("GEMINI_API_KEY no está definida")
        return None
    if not text or not text.strip():
        return None
    try:
        res = requests.post(
            EMBEDDING_URL,
            params={"key": GEMINI_API_KEY},
            json={"model": f"models/{EMBEDDING_MODEL}", "content": {"parts": [{"text": text[:8000]}]}},
            timeout=10,
        )
        res.raise_for_status()
        return res.json()["embedding"]["values"]
    except Exception as e:
        log.error(f"Error generando embedding: {e}")
        return None
