import os
import requests
import logging

log = logging.getLogger(__name__)

VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
VOYAGE_MODEL = "voyage-3-lite"
EMBEDDING_DIMS = 512


def get_embedding(text: str) -> list[float] | None:
    if not VOYAGE_API_KEY:
        log.error("VOYAGE_API_KEY no está definida")
        return None
    if not text or not text.strip():
        return None
    try:
        res = requests.post(
            VOYAGE_URL,
            headers={"Authorization": f"Bearer {VOYAGE_API_KEY}"},
            json={"model": VOYAGE_MODEL, "input": [text[:8000]]},
            timeout=10,
        )
        res.raise_for_status()
        values = res.json()["data"][0]["embedding"]
        log.info(f"Embedding generado, dims={len(values)}")
        return values
    except Exception as e:
        log.error(f"Error generando embedding: {e}")
        return None
