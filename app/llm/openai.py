import os
from app.llm.provider import LLMProvider


class OpenAIProvider(LLMProvider):

    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def generate(self, messages: list[dict]) -> str:
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
        )
        return response.choices[0].message.content or ""
