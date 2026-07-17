from datetime import datetime, timezone


def compile_base_context(sources: dict) -> dict:
    return {
        "type": "base",
        "sources": {
            "personal_log": sources.get("personal_log", ""),
            "cognitive_base": sources.get("cognitive_base", ""),
            "destilador": sources.get("destilador", ""),
        },
        "compiled_at": datetime.now(timezone.utc).isoformat(),
    }
