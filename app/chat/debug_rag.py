from fastapi import APIRouter, Depends
from app.core.jwt import require_auth
from app.core.encryption import decrypt
from app.memory.embeddings import get_query_embedding
from app.core.database import get_cursor

router = APIRouter(prefix="/chat", tags=["debug"])


@router.get("/debug/rag")
def debug_rag(
    query: str = "test",
    threshold: float = 0.50,
    user: dict = Depends(require_auth),
):
    """
    Debug del RAG. Parámetros:
      - query     : texto de búsqueda (default: "test")
      - threshold : similarity mínima (default: 0.50, usá 0 para ver todos los candidatos)
    Aplica el mismo filtro de producción: md.key LIKE 'memoria_hash_%'.
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
                  AND 1 - (mr.embedding <=> %s::vector) >= %s
                  AND md.key LIKE 'memoria_hash_%%'
                ORDER BY mr.embedding <=> %s::vector
                LIMIT 20
            """, (str(query_embedding), user["id"], str(query_embedding), threshold, str(query_embedding)))
            rows = cur.fetchall()
    except Exception as e:
        return {"error": str(e), "query": query}

    results = []
    for r in rows:
        raw = r["data"].get("message") or ""
        if raw:
            try:
                msg = decrypt(raw)
            except Exception:
                msg = raw  # no estaba encriptado, usar tal cual
        else:
            msg = ""

        results.append({
            "id": str(r["id"]),
            "document_key": r["document_key"],
            "document": r["document"],
            "role": r["data"].get("role"),
            "similarity": round(float(r["similarity"]), 4),
            "message": msg[:300],
        })

    return {
        "query": query,
        "threshold_used": threshold,
        "filter": "md.key LIKE 'memoria_hash_%'",
        "total_results": len(results),
        "results": results,
    }
