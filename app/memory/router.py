from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from app.core.jwt import require_auth
from app.core.database import get_cursor
from app.memory.service import (
    check_memory_status,
    create_user_memory,
    read_user_memory,
    write_user_memory,
    delete_user_document,
    rename_user_document,
    upload_txt_as_memory,
)
from pydantic import BaseModel

router = APIRouter(prefix="/memory", tags=["memory"])

MEMORY_ERRORS = {
    "not_found":     (status.HTTP_404_NOT_FOUND,  "Memoria no encontrada"),
    "unauthorized":  (status.HTTP_401_UNAUTHORIZED, "Acceso revocado."),
    "inaccessible":  (status.HTTP_403_FORBIDDEN,   "Documento no accesible."),
}

def _raise_memory_error(error: str):
    code, detail = MEMORY_ERRORS.get(error, (500, "Error inesperado"))
    raise HTTPException(status_code=code, detail=detail)


@router.get("/status")
def memory_status(user: dict = Depends(require_auth)):
    result = check_memory_status(user["id"])
    return {"user_id": user["id"], **result}


@router.get("")
def memory_read(user: dict = Depends(require_auth)):
    result = read_user_memory(user["id"])
    if result is None:
        _raise_memory_error("not_found")
    if "error" in result:
        _raise_memory_error(result["error"])
    return result


class WriteMemoryRequest(BaseModel):
    document: str
    name: str
    description: str
    row: dict

@router.post("")
def memory_write(body: WriteMemoryRequest, user: dict = Depends(require_auth)):
    try:
        return write_user_memory(user["id"], body.document, body.name, body.description, body.row)
    except ValueError as e:
        _raise_memory_error(str(e))


class RenameMemoryRequest(BaseModel):
    name: str

@router.delete("/{key}")
def memory_delete(key: str, user: dict = Depends(require_auth)):
    try:
        found = delete_user_document(user["id"], key)
    except ValueError as e:
        _raise_memory_error(str(e))
    if not found:
        _raise_memory_error("not_found")
    return {"deleted": True, "key": key}


@router.patch("/{key}/rename")
def memory_rename(key: str, body: RenameMemoryRequest, user: dict = Depends(require_auth)):
    try:
        found = rename_user_document(user["id"], key, body.name)
    except ValueError as e:
        _raise_memory_error(str(e))
    if not found:
        _raise_memory_error("not_found")
    return {"renamed": True, "key": key, "new_name": body.name}


@router.post("/upload-txt")
async def upload_txt(
    file: UploadFile = File(...),
    user: dict = Depends(require_auth),
    chat_id: str = Query(default=None),
):
    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .txt")

    # Límite plan free: 3 documentos por chat
    with get_cursor() as cur:
        if chat_id:
            cur.execute(
                "SELECT COUNT(*) as total FROM memory_documents WHERE user_id = %s AND chat_id = %s",
                [user["id"], chat_id]
            )
        else:
            cur.execute(
                "SELECT COUNT(*) as total FROM memory_documents WHERE user_id = %s",
                [user["id"]]
            )
        row = cur.fetchone()
        if row and row["total"] >= 3:
            raise HTTPException(status_code=403, detail="Límite de documentos alcanzado (plan free: 3)")

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="El archivo debe estar en UTF-8")

    return upload_txt_as_memory(user["id"], file.filename, text, chat_id=chat_id)
