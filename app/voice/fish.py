import os
import requests
import ormsgpack
from app.voice.provider import VoiceProvider

FISH_API_URL = "https://api.fish.audio/v1/tts"


class FishProvider(VoiceProvider):

    def __init__(self):
        self.api_key = os.getenv("FISH_AUDIO_API_KEY")
        self.voice_id = os.getenv("FISH_AUDIO_VOICE_ID")
        if not self.api_key:
            raise RuntimeError("FISH_AUDIO_API_KEY no configurada")
        if not self.voice_id:
            raise RuntimeError("FISH_AUDIO_VOICE_ID no configurada")

    def synthesize(self, text: str) -> bytes:
        payload = {
            "text": text,
            "reference_id": self.voice_id,
            "format": "mp3",
            "latency": "normal",
        }
        response = requests.post(
            FISH_API_URL,
            content=ormsgpack.packb(payload),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/msgpack",
                "model": "s2.1-pro-free",
            },
            timeout=30,
        )
        if not response.ok:
            print(f"Fish Audio error {response.status_code}: {response.text}")
            raise RuntimeError(f"Fish Audio error {response.status_code}: {response.text}")
        return response.content
