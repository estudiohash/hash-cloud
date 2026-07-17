from app.core.config import GOOGLE_CLIENT_ID  # fuerza load_dotenv
import os
import httpx
from app.llm.provider import LLMProvider


def _load_api_keys() -> list[str]:
    keys = []
    for i in range(1, 10):
        key = os.getenv(f"GEMINI_API_KEY_{i}")
        if key:
            keys.append(key)
    single = os.getenv("GEMINI_API_KEY")
    if single and single not in keys:
        keys.append(single)
    return keys


class GeminiProvider(LLMProvider):

    def __init__(self):
        self.keys = _load_api_keys()
        self.model = os.getenv("LLM_MODEL", "gemini-3.5-flash")
        if not self.keys:
            raise RuntimeError("No hay claves de Gemini definidas en las variables de entorno")

    def generate(self, messages: list[dict]) -> str:
        contents = [
            {
                "role": "user" if m["role"] == "user" else "model",
                "parts": [{"text": m["content"]}],
            }
            for m in messages
            if m["role"] != "system"
        ]

        system_parts = [m["content"] for m in messages if m["role"] == "system"]
        body = {"contents": contents}
        if system_parts:
            body["system_instruction"] = {"parts": [{"text": system_parts[0]}]}

        last_error = None
        for key in self.keys:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.model}:generateContent?key={key}"
            )
            try:
                response = httpx.post(url, json=body, timeout=60)
                if response.status_code == 429 or response.status_code == 503:
                    last_error = response.text
                    continue
                response.raise_for_status()
                data = response.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except httpx.HTTPStatusError as e:
                last_error = str(e)
                continue

        raise RuntimeError(f"Todas las claves fallaron. Último error: {last_error}")
