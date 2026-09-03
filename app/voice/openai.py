import os
import requests
from app.voice.provider import VoiceProvider

OPENAI_TTS_URL = "https://api.openai.com/v1/audio/speech"


class OpenAIVoiceProvider(VoiceProvider):

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY no configurada")

    def synthesize(self, text: str, voice_id: str | None = None) -> bytes:
        print(f">>> OpenAI TTS: voice={voice_id or chr(39)+"cedar"+chr(39)}, chars={len(text)}", flush=True)
        response = requests.post(
            OPENAI_TTS_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini-tts",
                "input": text,
                "voice": voice_id or "cedar",
                "response_format": "mp3",
                "instructions": "Hablá en español rioplatense argentino, con voz natural y fluida.",
            },
            timeout=30,
        )
        if not response.ok:
            print(f"OpenAI TTS error {response.status_code}: {response.text}")
            raise RuntimeError(f"OpenAI TTS error {response.status_code}: {response.text}")
        return response.content

    def synthesize_stream(self, text: str, voice_id: str | None = None, format: str = "mp3"):
        # OpenAI acepta "mp3" o "aac"
        response = requests.post(
            OPENAI_TTS_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini-tts",
                "input": text,
                "voice": voice_id or "cedar",
                "response_format": format,
                "instructions": "Hablá en español rioplatense argentino, con voz natural y fluida.",
            },
            timeout=60,
            stream=True,
        )
        if not response.ok:
            raise RuntimeError(f"OpenAI TTS error {response.status_code}: {response.text}")
        for chunk in response.iter_content(chunk_size=4096):
            if chunk:
                yield chunk
