# backfill_embeddings.py
# Ejecutar desde la raíz del proyecto:
#   python backfill_embeddings.py

import logging
import time
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

from app.core.database import get_cursor
from app.core.encryption import decrypt
from app.memory.embeddings import get_embedding

BATCH_SIZE = 10
PAUSE_BETWEEN_BATCHES = 0.5  # segundos


def fetch_rows_without_embedding(user_id: str) -> list[dict]:
    """Trae todas las filas sin embedding del usuario que tienen message en data."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT mr.id, mr.data
            FROM memory_rows mr
            JOIN memory_documents md ON md.id = mr.document_id
            WHERE md.user_id = %s
              AND mr.embedding IS NULL
              AND mr.data ? 'message'
              AND mr.data->>'message' IS NOT NULL
              AND mr.data->>'message' != ''
            ORDER BY mr.created_at ASC;
        """, (user_id,))
        return cur.fetchall()


def update_embedding(row_id, embedding: list[float]) -> None:
    """Actualiza SOLO el campo embedding de una fila existente."""
    with get_cursor() as cur:
        cur.execute(
            "UPDATE memory_rows SET embedding = %s::vector WHERE id = %s;",
            (str(embedding), row_id)
        )


def backfill(user_id: str):
    rows = fetch_rows_without_embedding(user_id)
    total = len(rows)

    print()
    print("=" * 50)
    print(f"  Usuario         : {user_id}")
    print(f"  Filas a procesar: {total}")
    print("=" * 50)

    if total == 0:
        log.info("Nada que procesar para este usuario.")
        return

    print()
    confirm = input(f"¿Confirmar backfill de {total} filas? [s/N]: ").strip().lower()
    if confirm != "s":
        print("Operación cancelada.")
        sys.exit(0)

    print()
    updated = 0
    failed = 0
    failed_ids = []

    for i in range(0, total, BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        log.info(f"Procesando lote {i // BATCH_SIZE + 1} ({len(batch)} filas)...")

        for row in batch:
            row_id = row["id"]
            try:
                raw_message = row["data"].get("message", "")
                if not raw_message:
                    log.warning(f"  Fila {row_id}: message vacío, salteando.")
                    continue

                try:
                    message = decrypt(raw_message)
                except Exception:
                    message = raw_message

                embedding = get_embedding(message)
                if not embedding:
                    log.warning(f"  Fila {row_id}: get_embedding() devolvió None, salteando.")
                    failed += 1
                    failed_ids.append(row_id)
                    continue

                update_embedding(row_id, embedding)
                log.info(f"  Fila {row_id}: OK ({len(embedding)} dims).")
                updated += 1

            except Exception as e:
                log.error(f"  Fila {row_id}: ERROR — {e}")
                failed += 1
                failed_ids.append(row_id)

        if i + BATCH_SIZE < total:
            time.sleep(PAUSE_BETWEEN_BATCHES)

    # Verificación final contra BD
    with get_cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) AS pending
            FROM memory_rows mr
            JOIN memory_documents md ON md.id = mr.document_id
            WHERE md.user_id = %s
              AND mr.embedding IS NULL;
        """, (user_id,))
        pending = cur.fetchone()["pending"]

    print()
    print("=" * 50)
    print(f"  RESUMEN")
    print(f"  Total procesadas : {total}")
    print(f"  Actualizadas OK  : {updated}")
    print(f"  Fallidas         : {failed}")
    print(f"  Pendientes en BD : {pending}")
    if failed_ids:
        print(f"  IDs fallidos     : {failed_ids}")
    print("=" * 50)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python backfill_embeddings.py <user_id>")
        sys.exit(1)

    user_id = sys.argv[1]
    backfill(user_id)
