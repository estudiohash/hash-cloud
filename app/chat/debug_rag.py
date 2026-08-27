from fastapi import APIRouter, Depends
from app.core.jwt import require_auth
from app.core.encryption import decrypt
from app.memory.embeddings import get_query_embedding
from app.core.database import get_cursor

router = APIRouter(prefix="/chat", tags=["debug"])


@router.get("/debug/rag")
def debug_rag(query: str = "test", user: dict = Depends(require_auth)):
    """
    Muestra exactamente qué filas devolvería search_memory_by_embedding()
    con el mismo filtro que usa producción:
      - role = 'user' OR role IS NULL (excluye respuestas del assistant)
      - embedding IS NOT NULL
      - similarity >= 0.50
      - top_k = 20
    """
    query_embedding = get_query_embedding(query)
    if not query_embedding:
        return {"error": "No se pudo generar embedding para la query", "query": query}

    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT
                    mr.id,
                    md.name AS document,
                    md.key  AS document_key,
                    mr.data,
                    1 - (mr.embedding <=> %s::vector) AS similarity
                FROM memory_rows mr
                JOIN memory_documents md ON md.id = mr.document_id
                WHERE md.user_id = %s
                  AND mr.embedding IS NOT NULL
                  AND 1 - (mr.embedding <=> %s::vector) >= 0.50
                  AND (mr.data->>'role' = 'user' OR mr.data->>'role' IS NULL)
                ORDER BY mr.embedding <=> %s::vector
                LIMIT 20
            """, (str(query_embedding), user["id"], str(query_embedding), str(query_embedding)))
            rows = cur.fetchall()
    except Exception as e:
        return {"error": str(e), "query": query}

    results = []
    for r in rows:
        msg = r["data"].get("message", "")
        try:
            msg = decrypt(msg)
        except Exception:
            pass
        results.append({
            "id": str(r["id"]),
            "document": r["document"],
            "document_key": r["document_key"],
            "role": r["data"].get("role"),
            "similarity": round(float(r["similarity"]), 4),
            "message_preview": msg[:200],
        })

    return {
        "query": query,
        "threshold": 0.50,
        "top_k": 20,
        "filter": "role = 'user' OR role IS NULL",
        "total_results": len(results),
        "results": results,
    }
