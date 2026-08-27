# app/chat/debug_rag.py
# Endpoint temporal de diagnóstico RAG.
# NO modifica ningún dato. Solo lectura.

from fastapi import APIRouter, Depends, Query
from app.core.jwt import require_auth
from app.core.encryption import decrypt
from app.context.provider import get_hash_sources, STYLES, DEFAULT_STYLE
from app.compiler.base_compiler import compile_base_context
from app.compiler.style_compiler import compile_style_context
from app.memory.embeddings import get_query_embedding
from app.core.database import get_cursor

debug_router = APIRouter(prefix="/debug", tags=["debug"])

SEARCH_THRESHOLD = 0.50


def _raw_search_all(user_id: str, query: str, limit: int = 10) -> list[dict]:
    """
    Recupera los top-N resultados SIN threshold para mostrar antes/después.
    """
    query_embedding = get_query_embedding(query)
    if not query_embedding:
        return []
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT
                    md.key        AS doc_key,
                    md.name       AS doc_name,
                    mr.id         AS row_id,
                    mr.data       AS data,
                    mr.created_at AS created_at,
                    1 - (mr.embedding <=> %s::vector) AS similarity
                FROM memory_rows mr
                JOIN memory_documents md ON md.id = mr.document_id
                WHERE md.user_id = %s
                  AND mr.embedding IS NOT NULL
                ORDER BY mr.embedding <=> %s::vector
                LIMIT %s
            """, (str(query_embedding), user_id, str(query_embedding), limit))
            return cur.fetchall()
    except Exception:
        return []


def _count_rows(user_id: str) -> list:
    with get_cursor() as cur:
        cur.execute("""
            SELECT
                md.key,
                md.name,
                COUNT(mr.id)                                         AS total_rows,
                COUNT(mr.id) FILTER (WHERE mr.embedding IS NOT NULL) AS rows_with_embedding
            FROM memory_documents md
            LEFT JOIN memory_rows mr ON mr.document_id = md.id
            WHERE md.user_id = %s
            GROUP BY md.key, md.name
            ORDER BY md.name
        """, [user_id])
        return cur.fetchall()


@debug_router.get("/rag")
def debug_rag(
    query: str = Query(...),
    mode: str = Query("conspiranoico"),
    limit: int = Query(10),
    threshold: float = Query(SEARCH_THRESHOLD),
    user: dict = Depends(require_auth),
):
    user_id = user["id"]

    # Mode
    mode_resolved = mode if mode in STYLES else DEFAULT_STYLE

    # Estilo y contexto
    sources = get_hash_sources(mode_resolved)
    style_text = compile_style_context(sources)["sources"]["style"]
    base_ctx = compile_base_context(sources)

    # Búsqueda sin threshold (para mostrar todos los candidatos)
    raw_rows = _raw_search_all(user_id, query, limit=limit)

    all_results = []
    for r in raw_rows:
        msg = r["data"].get("message", "")
        if not msg:
            continue
        try:
            msg = decrypt(msg)
        except Exception:
            pass
        truncated = msg.strip()[:500]
        all_results.append({
            "row_id":      r["row_id"],
            "doc_key":     r["doc_key"],
            "doc_name":    r["doc_name"],
            "similarity":  round(float(r["similarity"]), 4),
            "above_threshold": float(r["similarity"]) >= threshold,
            "text_preview": truncated[:200] + ("…" if len(truncated) > 200 else ""),
            "entry_chars": len(f"[{r['doc_name']}]\n{truncated}"),
            "created_at":  r["created_at"].isoformat(),
        })

    results_after = [r for r in all_results if r["above_threshold"]]

    # Reconstruir memory block solo con los que pasan el threshold
    memory_total_chars = sum(r["entry_chars"] for r in results_after)
    memory_block = "\n\n".join(
        f"[{r['doc_name']}]\n{r['text_preview']}" for r in results_after
    ) if results_after else ""

    system_prompt = (
        f"Fecha y hora actual: {base_ctx['fecha_actual']}\n\n"
        + (f"Memoria relevante:\n{memory_block}\n\n" if memory_block else "")
        + f"Identidad de HASH:\n{base_ctx['sources']['cognitive_base']}\n\n"
        f"Log personal:\n{base_ctx['sources']['personal_log']}\n\n"
        f"Destilador:\n{base_ctx['sources']['destilador']}\n\n"
        f"Estilo:\n{style_text}"
    )

    doc_stats = _count_rows(user_id)

    return {
        "query": query,

        "mode": {
            "received":     mode,
            "resolved":     mode_resolved,
            "was_fallback": mode_resolved != mode,
        },

        "style": {
            "chars":   len(style_text),
            "preview": style_text[:300] + ("…" if len(style_text) > 300 else ""),
        },

        "memories": {
            "threshold":                  threshold,
            "retrieved_before_threshold": len(all_results),
            "retrieved_after_threshold":  len(results_after),
            "total_chars_after":          memory_total_chars,
            "rows_in_db":                 sum(d["total_rows"] for d in doc_stats),
            "rows_with_embedding":        sum(d["rows_with_embedding"] for d in doc_stats),
            "results": all_results,
        },

        "system_prompt": {
            "total_chars": len(system_prompt),
            "memory_pct":  round(memory_total_chars / len(system_prompt) * 100, 1) if system_prompt else 0,
            "style_pct":   round(len(style_text) / len(system_prompt) * 100, 1) if system_prompt else 0,
        },

        "db_documents": [
            {
                "key":                 d["key"],
                "name":                d["name"],
                "total_rows":          d["total_rows"],
                "rows_with_embedding": d["rows_with_embedding"],
            }
            for d in doc_stats
        ],
    }
