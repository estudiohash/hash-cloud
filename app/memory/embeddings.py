import os
import requests
import logging

log = logging.getLogger(__name__)

EMBEDDING_MODELS = [
    "gemini-embedding-exp-03-07",
    "text-embedding-004",
    "embedding-001",
]

def _get_keys() -> list[str]:
    keys = []
    for i in range(1, 10):
        k = os.getenv(f"GEMINI_API_KEY_{i}")
        if k:
            keys.append(k)
    single = os.getenv("GEMINI_API_KEY")
    if single and single not in keys:
        keys.append(single)
    return keys


def get_embedding(text: str) -> list[float] | None:
    """Genera un embedding para el texto dado probando modelos disponibles."""
    keys = _get_keys()
    if not keys or not text or not text.strip():
        return None
    for model in EMBEDDING_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent"
        for key in keys:
            try:
                res = requests.post(
                    url,
                    params={"key": key},
                    json={"model": f"models/{model}", "content": {"parts": [{"text": text[:8000]}]}},
                    timeout=10,
                )
                if res.status_code == 404:
                    break  # modelo no existe, probar el siguiente
                res.raise_for_status()
                values = res.json()["embedding"]["values"]
                log.info(f"Embedding generado con modelo {model}, dims={len(values)}")
                return values
            except Exception as e:
                log.error(f"Error con modelo {model}: {e}")
    log.error("No se pudo generar embedding con ningún modelo")
    return None
