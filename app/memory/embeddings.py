import os
import requests
import logging

log = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_URL = "https://api.openai.com/v1/embeddings"

# text-embedding-3-small: modelo estable de OpenAI (desde ene 2024).
# Dimensión: 1536 floats.
# No requiere input_type: el mismo endpoint sirve para indexar y buscar.
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_EMBEDDING_DIMS = 1536


def get_embedding(text: str, input_type: str = "passage") -> list[float] | None:
    """
    Genera un embedding con OpenAI text-embedding-3-small.

    El parámetro input_type se conserva por compatibilidad con el resto del
    código (repository.py llama get_embedding con input_type="passage" y
    get_query_embedding llama con input_type="query"), pero OpenAI no hace
    distinción asimétrica: ambos tipos producen el mismo vector normalizado.
    No se envía al API.

    Dimensión de salida: 1536.
    """
    if not OPENAI_API_KEY:
        log.error("OPENAI_API_KEY no está definida")
        return None
    if not text or not text.strip():
        return None
    try:
        res = requests.post(
            OPENAI_URL,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENAI_EMBEDDING_MODEL,
                "input": text[:8000],
                "encoding_format": "float",
            },
            timeout=15,
        )
        res.raise_for_status()
        values = res.json()["data"][0]["embedding"]
        log.info(f"Embedding generado OK — model={OPENAI_EMBEDDING_MODEL}, dims={len(values)}, input_type={input_type}")
        return values
    except Exception as e:
        log.error(f"Error generando embedding (input_type={input_type}): {e}")
        return None


def get_query_embedding(text: str) -> list[float] | None:
    """Atajo para embeddings de búsqueda. Con OpenAI es idéntico a get_embedding."""
    return get_embedding(text, input_type="query")
