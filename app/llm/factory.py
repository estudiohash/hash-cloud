import os
from app.llm.provider import LLMProvider


def get_llm_provider() -> LLMProvider:
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()

    if provider == "gemini":
        from app.llm.gemini import GeminiProvider
        return GeminiProvider()
    elif provider == "openai":
        from app.llm.openai import OpenAIProvider
        return OpenAIProvider()
    elif provider == "anthropic":
        from app.llm.anthropic import AnthropicProvider
        return AnthropicProvider()
    elif provider == "grok":
        from app.llm.grok import GrokProvider
        return GrokProvider()
    elif provider == "ollama":
        from app.llm.ollama import OllamaProvider
        return OllamaProvider()
    else:
        raise ValueError(f"Proveedor LLM no soportado: {provider}")
