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
    add_row(document_id, {"role": role, "message": content}, with_embedding=True)


def export_memory(user_id: str) -> str:
    """
    Devuelve toda la memoria del usuario como texto plano limpio.
    Sin headers de documento ni prefijos [user]/[assistant].
    Conserva todo el contenido y los saltos entre bloques.
    """
    if not user_exists(user_id):
        return ""
    documents = get_documents_with_rows(user_id)
    blocks = []
    for doc in documents:
        if doc["key"].startswith("memoria_hash_"):
            continue
        for row in doc["rows"]:
            msg = row.get("message", "").strip()
            if msg:
                blocks.append(msg)
    return "\n\n".join(blocks)


def upload_txt_as_memory(user_id: str, filename: str, content: str, chat_id: str | None = None) -> dict:
    if not user_exists(user_id):
        create_user(user_id)

    import time
    # Clave única por timestamp para no pisar archivos anteriores del mismo nombre
    key = filename.replace(".txt", "").replace(" ", "_").lower() + "_" + str(int(time.time()))
    name = filename.replace(".txt", "")
    description = f"Cargado desde archivo: {filename}"

    document_id, created = get_or_create_document(user_id, key, name, description, chat_id=chat_id)

    # Un mensaje = un chunk. No acumular mensajes distintos en el mismo embedding.
    # Solo dividir si un mensaje individual supera MAX_CHARS.
    MAX_CHARS = 6000
    paragraphs = [p.strip() for p in content.strip().split("\n\n") if p.strip()]

    chunks = []
    for para in paragraphs:
        if len(para) <= MAX_CHARS:
            chunks.append(para)
        else:
            for i in range(0, len(para), MAX_CHARS):
                part = para[i:i + MAX_CHARS].strip()
                if part:
                    chunks.append(part)

    for chunk_text in chunks:
        if chunk_text.strip():
            add_row(document_id, {"message": chunk_text}, with_embedding=True)

    return {"document": key, "created": created, "rows_added": len(chunks)}
