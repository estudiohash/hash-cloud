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

router = APIRouter(prefix="/memory", tags=["memory"])  # v12

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

    # Obtener documentos del usuario
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT id, name FROM memory_documents
                WHERE user_id = %s AND key NOT LIKE 'chat_log%%'
                ORDER BY created_at ASC
            """, (user["id"],))
            docs = cur.fetchall()
    except Exception as e:
        import traceback; tb = traceback.format_exc(); print("GRAPH DB ERROR:", tb)
        raise HTTPException(status_code=500, detail=tb)

    if not docs:
        return {"nodes": [], "edges": []}

    doc_names = [d["name"] for d in docs]

    # Por cada tema, buscar chunks relevantes por embedding
    fragments = []
    for doc in docs:
        results = search_memory_by_embedding(user["id"], doc["name"], limit=2)
        for r in results:
            data = r.get("data", {}) if isinstance(r, dict) else {}
            msg = data.get("message", "") if isinstance(data, dict) else ""
            if not msg:
                continue
            try:
                msg = decrypt(msg)
            except Exception:
                pass
            fragments.append(f"[{doc['name']}]\n{msg[:2000]}")

    if not fragments:
        return {"nodes": [], "edges": []}

    memory_text = "\n\n".join(fragments)[:10000]

    # Llamar a Gemini para extraer el grafo
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY no configurada")

    temas_lista = "\n".join(f"- {n}" for n in doc_names)
    prompt = f"""Analizá esta memoria y generá un grafo de conexiones.

TEMAS OBLIGATORIOS (cada uno DEBE ser un nodo principal):
{temas_lista}

MEMORIA:
{memory_text}

Devolvé SOLO un JSON válido, sin texto adicional:
{{
  "nodes": [
    {{"id": "cerebro", "label": "Cerebro", "main": true}},
    {{"id": "tema1", "label": "Arquitectura de Software", "main": true}},
    {{"id": "concepto1", "label": "Concepto compartido", "sub": true, "parent": "tema1"}}
  ],
  "edges": [
    {{"from": "cerebro", "to": "tema1"}},
    {{"from": "tema1", "to": "concepto1"}},
    {{"from": "tema1", "to": "tema2"}}
  ]
}}

Reglas ESTRICTAS:
- Nodo central: id "cerebro", label "Cerebro"
- OBLIGATORIO: creá exactamente un nodo main por cada tema de la lista, con ese nombre exacto como label
- Conectá cerebro con todos los nodos principales
- Buscá 2-4 conceptos que aparezcan en múltiples temas y hacelos subnodos conectados a todos esos temas
- Conectá directamente los temas que comparten muchos conceptos
- Labels cortos (1-3 palabras)
- Solo JSON, sin markdown"""

    try:
        model = os.getenv("LLM_MODEL", "gemini-3.1-flash-lite")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        res = requests.post(
            url,
            params={"key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        )
        res.raise_for_status()
        gemini_json = res.json()
        if not gemini_json.get("candidates"):
            raise HTTPException(status_code=500, detail=f"Gemini sin candidates: {gemini_json}")
        text = gemini_json["candidates"][0]["content"]["parts"][0]["text"].strip()
        # Limpiar markdown si viene
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        import json
        graph = json.loads(text)
        return graph
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print("GRAPH ERROR:", tb)
        raise HTTPException(status_code=500, detail=tb)
