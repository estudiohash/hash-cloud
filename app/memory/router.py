from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import Response
from app.core.jwt import require_auth
from app.memory.service import (
    check_memory_status,
    create_user_memory,
    read_user_memory,
    write_user_memory,
    delete_user_document,
    rename_user_document,
    upload_txt_as_memory,
    export_memory,
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


@router.get("/export")
def memory_export(user: dict = Depends(require_auth)):
    text = export_memory(user["id"])
    return Response(
        content=text.encode("utf-8"),
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=memoria_hash.txt"}
    )


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


@router.post("/upload")
async def upload_memory(
    file: UploadFile = File(...),
    user: dict = Depends(require_auth),
):
    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .txt")

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="El archivo debe estar en UTF-8")

    return upload_txt_as_memory(user["id"], file.filename, text, chat_id=None)


@router.get("/graph")
async def memory_graph(user: dict = Depends(require_auth)):
    """Analiza la memoria con Gemini y devuelve nodos y conexiones para el grafo neural."""
    import os, requests
    from app.memory.repository import search_memory_by_embedding
    from app.core.encryption import decrypt
    from app.core.database import get_cursor

    # Leer toda la memoria (solo documentos, no chat_log)
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT md.name, mr.data
                FROM memory_rows mr
                JOIN memory_documents md ON md.id = mr.document_id
                WHERE md.user_id = %s AND md.key NOT LIKE 'chat_log%'
                ORDER BY mr.created_at ASC
                LIMIT 20
            """, [user["id"]])
            rows = cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not rows:
        return {"nodes": [], "edges": []}

    # Desencriptar y armar el texto
    fragments = []
    for r in rows:
        msg = r["data"].get("message", "")
        if not msg:
            continue
        try:
            msg = decrypt(msg)
        except Exception:
            pass
        fragments.append(f"[{r['name']}]\n{msg[:3000]}")

    memory_text = "\n\n".join(fragments)[:12000]

    # Llamar a Gemini para extraer el grafo
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY no configurada")

    prompt = f"""Analizá esta memoria personal y extraé un grafo de conceptos.

MEMORIA:
{memory_text}

Devolvé SOLO un JSON válido con esta estructura exacta, sin texto adicional:
{{
  "nodes": [
    {{"id": "cerebro", "label": "Cerebro", "main": true}},
    {{"id": "nodo1", "label": "Nombre corto", "main": false}},
    {{"id": "subnodo1", "label": "Concepto", "sub": true, "parent": "nodo1"}}
  ],
  "edges": [
    {{"from": "cerebro", "to": "nodo1"}},
    {{"from": "nodo1", "to": "subnodo1"}}
  ]
}}

Reglas:
- Siempre incluir el nodo central con id "cerebro" y label "Cerebro"
- 5 a 8 nodos principales (main: true) con temas importantes de la memoria
- 3 a 5 subnodos por nodo principal (sub: true) con conceptos específicos encontrados
- Conectar cerebro con todos los nodos principales
- Conectar nodos principales entre sí si comparten ideas
- Conectar cada subnodo con su nodo padre
- Los labels deben ser cortos (1-3 palabras máximo)
- Solo JSON, sin markdown, sin explicaciones"""

    try:
        model = "gemini-2.0-flash-lite"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        res = requests.post(
            url,
            params={"key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        )
        res.raise_for_status()
        text = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        # Limpiar markdown si viene
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        import json
        graph = json.loads(text)
        return graph
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception(f"Error en /memory/graph: {e}")
        raise HTTPException(status_code=500, detail=f"Error generando grafo: {e}")
