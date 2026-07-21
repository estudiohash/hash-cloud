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


def create_user_memory(user_id: str, access_token: str | None = None, refresh_token: str | None = None) -> dict:
    """
    Ya no depende de Drive: crea el usuario directo en Postgres.
    access_token queda sin uso (se mantiene el parámetro por compatibilidad con el router/auth).
    Si viene refresh_token, se guarda igual — útil si en el futuro se necesita para otra integración de Google.
    """
    create_user(user_id)
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


def upload_txt_as_memory(user_id: str, filename: str, content: str) -> dict:
    if not user_exists(user_id):
        create_user(user_id)

    import time
    # Clave única por timestamp para no pisar archivos anteriores del mismo nombre
    key = filename.replace(".txt", "").replace(" ", "_").lower() + "_" + str(int(time.time()))
    name = filename.replace(".txt", "")
    description = f"Cargado desde archivo: {filename}"

    document_id, created = get_or_create_document(user_id, key, name, description)

    # Guardar el contenido completo como un solo bloque
    add_row(document_id, {"message": content.strip()})

    return {"document": key, "created": created, "rows_added": 1}
