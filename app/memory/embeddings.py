import os
import time
import requests
import logging

log = logging.getLogger(__name__)

VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
VOYAGE_MODEL = "voyage-3-lite"


def get_embedding(text: str) -> list[float] | None:
    log.info(f"get_embedding llamado, key={'OK' if VOYAGE_API_KEY else 'FALTA'}, texto={len(text) if text else 0} chars")
    if not VOYAGE_API_KEY:
        log.error("VOYAGE_API_KEY no está definida")
        return None
    if not text or not text.strip():
        return None
    for attempt in range(3):
        try:
            res = requests.post(
                VOYAGE_URL,
                headers={"Authorization": f"Bearer {VOYAGE_API_KEY}"},
                json={"model": VOYAGE_MODEL, "input": [text[:8000]]},
                timeout=15,
            )
            log.info(f"Voyage respuesta: {res.status_code}")
            if res.status_code == 429:
                wait = 2 ** attempt
                log.warning(f"Rate limit, esperando {wait}s...")
                time.sleep(wait)
                continue
            res.raise_for_status()
            values = res.json()["data"][0]["embedding"]
            log.info(f"Embedding generado OK, dims={len(values)}")
            return values
        except Exception as e:
            log.error(f"Error generando embedding: {e}")
            return None
    log.error("Rate limit persistente")
    return None
