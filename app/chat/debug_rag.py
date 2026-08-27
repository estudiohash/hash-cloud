# app/chat/debug_rag.py
# Endpoint temporal de diagnóstico RAG.
# NO modifica ningún dato. Solo lectura.
# Agregar en main.py: from app.chat.debug_rag import debug_router
#                     app.include_router(debug_router)

from fastapi import APIRouter, Depends, Query
from app.core.jwt import require_auth
from app.core.encryption import decrypt
from app.context.provider import get_hash_sources, STYLES, DEFAULT_STYLE
from app.compiler.base_compiler import compile_base_context
from app.compiler.style_compiler import compile_style_context
from app.memory.embeddings import get_embedding
from app.core.database import get_cursor

debug_router = APIRouter(prefix="/debug", tags=["debug"])


def _raw_search_with_scores(user_id: str, query: str, limit: int = 10) -> list[dict]:
    """
    Replica exactamente search_memory_by_embedding del repository
    pero devuelve también el similarity score y metadatos completos.
    Sin threshold: muestra todo lo que ve el sistema real.
    """
    query_embedding = get_embedding(query)
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
    except Exception as e:
        return []


def _count_rows(user_id: str) -> dict:
    """Conteo de filas totales y con embedding, por documento."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT
                md.key,
                md.name,
                COUNT(mr.id)                                      AS total_rows,
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
    query: str = Query(..., description="Texto de prueba, igual al mensaje que mandarías al chat"),
    mode: str = Query("conspiranoico", description="Modo de estilo: conspiranoico, analista, terapeuta, zen, hacker, masivo"),
    limit: int = Query(10, description="Cantidad de recuerdos a recuperar (mismo default que el sistema real)"),
    user: dict = Depends(require_auth),
):
    """
    Diagnóstico completo del pipeline RAG para un usuario autenticado.
    No escribe nada, no modifica nada.

    Uso:
      GET /debug/rag?query=quien es mateo&mode=analista
    """
    user_id = user["id"]

    # ── 1. Mode resolution ────────────────────────────────────────────────────
    mode_resolved = mode if mode in STYLES else DEFAULT_STYLE
    mode_was_fallback = mode_resolved != mode

    # ── 2. Estilo ─────────────────────────────────────────────────────────────
    sources = get_hash_sources(mode_resolved)
    style_text = compile_style_context(sources)["sources"]["style"]
    base_ctx = compile_base_context(sources)

    # ── 3. Búsqueda RAG con scores ────────────────────────────────────────────
    raw_rows = _raw_search_with_scores(user_id, query, limit=limit)

    memories = []
    memory_total_chars = 0

    for r in raw_rows:
        msg = r["data"].get("message", "")
        if not msg:
            continue
        try:
            msg = decrypt(msg)
        except Exception:
            pass

        # El sistema real trunca a 500 chars
        truncated = msg.strip()[:500]
        entry_text = f"[{r['doc_name']}]\n{truncated}"
        entry_chars = len(entry_text)
        memory_total_chars += entry_chars

        memories.append({
            "row_id":        r["row_id"],
            "doc_key":       r["doc_key"],
            "doc_name":      r["doc_name"],
            "similarity":    round(float(r["similarity"]), 4),
            "text_preview":  truncated[:200] + ("…" if len(truncated) > 200 else ""),
            "text_full_chars": len(truncated),
            "entry_chars":   entry_chars,   # incluye "[doc_name]\n"
            "created_at":    r["created_at"].isoformat(),
        })

    # ── 4. Reconstruir system prompt exacto ───────────────────────────────────
    memory_block = "\n\n".join(
        f"[{m['doc_name']}]\n{m['text_preview']}" for m in memories
    ) if memories else ""

    system_prompt = (
        f"Fecha y hora actual: {base_ctx['fecha_actual']}\n\n"
        + (f"Memoria relevante:\n{memory_block}\n\n" if memory_block else "")
        + f"Identidad de HASH:\n{base_ctx['sources']['cognitive_base']}\n\n"
        f"Log personal:\n{base_ctx['sources']['personal_log']}\n\n"
        f"Destilador:\n{base_ctx['sources']['destilador']}\n\n"
        f"Estilo:\n{style_text}"
    )

    # ── 5. Conteo de memoria del usuario ─────────────────────────────────────
    doc_stats = _count_rows(user_id)
    total_rows_in_db = sum(d["total_rows"] for d in doc_stats)
    total_with_embedding = sum(d["rows_with_embedding"] for d in doc_stats)

    # ── 6. Respuesta ─────────────────────────────────────────────────────────
    return {
        "query": query,

        "mode": {
            "received":    mode,
            "resolved":    mode_resolved,
            "was_fallback": mode_was_fallback,
        },

        "style": {
            "chars": len(style_text),
            "preview": style_text[:300] + ("…" if len(style_text) > 300 else ""),
        },

        "memories": {
            "retrieved_count":    len(memories),
            "total_chars":        memory_total_chars,
            "rows_in_db":         total_rows_in_db,
            "rows_with_embedding": total_with_embedding,
            "results": memories,
        },

        "system_prompt": {
            "total_chars":   len(system_prompt),
            "memory_pct":    round(memory_total_chars / len(system_prompt) * 100, 1) if system_prompt else 0,
            "style_pct":     round(len(style_text) / len(system_prompt) * 100, 1) if system_prompt else 0,
        },

        "db_documents": [
            {
                "key":                d["key"],
                "name":               d["name"],
                "total_rows":         d["total_rows"],
                "rows_with_embedding": d["rows_with_embedding"],
            }
            for d in doc_stats
        ],
    }
