from app.memory.repository import (
    user_exists,
    create_user,
    get_or_create_document,
    add_row,
    get_index,
    get_documents_with_rows,
    delete_document,
    rename_document,
)
from app.core.credentials_repository import save_refresh_token


# ─────────────────────────────────────────────
# API pública — misma forma que antes (Sheets/Drive),
# así el router no necesita cambios.
# ─────────────────────────────────────────────

def check_memory_status(user_id: str) -> dict:
    if not user_exists(user_id):
        return {"status": "not_found"}
    return {"status": "active"}


def create_user_memory(user_id: str, access_token: str | None = None, refresh_token: str | None = None, email: str | None = None) -> dict:
    """
    Ya no depende de Drive: crea el usuario directo en Postgres.
    """
    create_user(user_id, email=email)
    if refresh_token:
        save_refresh_token(user_id, refresh_token)
    return {"user_id": user_id}


def read_user_memory(user_id: str) -> dict | None:
    if not user_exists(user_id):
        return None

    return {
        "id": user_id,
        "source": "postgres",
        "index": get_index(user_id),
        "documents": get_documents_with_rows(user_id),
    }


def write_user_memory(user_id: str, document: str, name: str, description: str, row: dict) -> dict:
    if not user_exists(user_id):
        raise ValueError("not_found")

    document_id, created = get_or_create_document(user_id, document, name, description)
    row_with_ts = add_row(document_id, row)

    return {"document": document, "created": created, "row": row_with_ts}


def delete_user_document(user_id: str, key: str) -> bool:
    if not user_exists(user_id):
        raise ValueError("not_found")
    return delete_document(user_id, key)


def rename_user_document(user_id: str, key: str, new_name: str) -> bool:
    if not user_exists(user_id):
        raise ValueError("not_found")
    return rename_document(user_id, key, new_name)


def save_message_to_memory(user_id: str, role: str, content: str) -> None:
    """Guarda cada mensaje del chat en memoria en tiempo real."""
    if not user_exists(user_id):
        create_user(user_id)
    document_id, _ = get_or_create_document(
        user_id, "chat_log", "Chat log", "Historial automático de conversaciones"
    )
    add_row(document_id, {"role": role, "message": content})


def export_memory(user_id: str) -> str:
    """Devuelve toda la memoria del usuario como texto plano."""
    if not user_exists(user_id):
        return ""
    documents = get_documents_with_rows(user_id)
    lines = []
    for doc in documents:
        lines.append(f"=== {doc['name']} ===")
        for row in doc["rows"]:
            role = row.get("role", "")
            msg = row.get("message", "")
            if role:
                lines.append(f"[{role}] {msg}")
            else:
                lines.append(msg)
        lines.append("")
    return "\n".join(lines)


def upload_txt_as_memory(user_id: str, filename: str, content: str, chat_id: str | None = None) -> dict:
    if not user_exists(user_id):
        create_user(user_id)

    import time

    topics = _split_into_topics_with_llm(content)

    if topics:
        docs_created = 0
        rows_added = 0
        for topic in topics:
            name = topic.get("name", "Sin nombre")[:80]
            topic_content = topic.get("content", "").strip()
            if not topic_content:
                continue
            key = name.lower().replace(" ", "_")[:60] + "_" + str(int(time.time()))
            document_id, created = get_or_create_document(user_id, key, name, f"Tema extraído de {filename}", chat_id=chat_id)
            add_row(document_id, {"message": topic_content}, with_embedding=True)
            if created:
                docs_created += 1
            rows_added += 1
        return {"documents_created": docs_created, "rows_added": rows_added, "split_by": "llm"}

    # Fallback: un solo documento
    key = filename.replace(".txt", "").replace(" ", "_").lower() + "_" + str(int(time.time()))
    name = filename.replace(".txt", "")
    document_id, created = get_or_create_document(user_id, key, name, f"Cargado desde {filename}", chat_id=chat_id)
    lines = content.strip().splitlines()
    chunks = [lines[i:i+1600] for i in range(0, len(lines), 1600)]
    for chunk in chunks:
        chunk_text = "\n".join(chunk).strip()
        if chunk_text:
            add_row(document_id, {"message": chunk_text}, with_embedding=True)
    return {"document": key, "created": created, "rows_added": len(chunks), "split_by": "fallback"}



def _split_into_topics_with_llm(content: str) -> list | None:
    import os, requests, json
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("LLM_MODEL", "gemini-3.1-flash-lite")
    if not api_key:
        return None
    prompt = f"""Analizá este texto y dividilo en temas principales.

TEXTO:
{content[:12000]}

Devolvé SOLO un JSON válido, sin texto adicional:
[
  {{"name": "Nombre del tema", "content": "Todo el contenido relevante de ese tema"}},
  {{"name": "Otro tema", "content": "Contenido..."}}
]

Reglas:
- Entre 3 y 10 temas
- Nombres cortos (1-3 palabras)
- Incluí todo el contenido original en algún tema, sin perder información
- Solo JSON, sin markdown"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        res = requests.post(url, params={"key": api_key}, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
        res.raise_for_status()
        gemini = res.json()
        if not gemini.get("candidates"):
            return None
        text = gemini["candidates"][0]["content"]["parts"][0]["text"].strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception:
        return None
