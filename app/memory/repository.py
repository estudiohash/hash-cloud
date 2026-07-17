from datetime import datetime, timezone
from psycopg2.extras import Json
from app.core.database import get_cursor


def user_exists(user_id: str) -> bool:
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM memory_users WHERE user_id = %s;", (user_id,))
        return cur.fetchone() is not None


def create_user(user_id: str) -> None:
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO memory_users (user_id, created_at)
            VALUES (%s, %s)
            ON CONFLICT (user_id) DO NOTHING;
            """,
            (user_id, datetime.now(timezone.utc)),
        )


def get_or_create_document(user_id: str, key: str, name: str, description: str) -> tuple[str, bool]:
    """Devuelve (document_id, created). created=True si se acaba de crear."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT id FROM memory_documents WHERE user_id = %s AND key = %s;",
            (user_id, key),
        )
        row = cur.fetchone()
        if row:
            return str(row["id"]), False

        cur.execute(
            """
            INSERT INTO memory_documents (user_id, key, name, description, created_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (user_id, key, name, description, datetime.now(timezone.utc)),
        )
        new_id = cur.fetchone()["id"]
        return str(new_id), True


def add_row(document_id: str, data: dict) -> dict:
    created_at = datetime.now(timezone.utc)
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO memory_rows (document_id, data, created_at)
            VALUES (%s, %s, %s)
            RETURNING id;
            """,
            (document_id, Json(data), created_at),
        )
    return {**data, "created_at": created_at.isoformat()}


def get_index(user_id: str) -> list[dict]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, name, description, created_at
            FROM memory_documents
            WHERE user_id = %s
            ORDER BY created_at ASC;
            """,
            (user_id,),
        )
        rows = cur.fetchall()
    return [
        {
            "id": str(r["id"]),
            "name": r["name"],
            "description": r["description"],
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]


def get_documents_with_rows(user_id: str) -> list[dict]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, key, name, description, created_at
            FROM memory_documents
            WHERE user_id = %s
            ORDER BY created_at ASC;
            """,
            (user_id,),
        )
        documents = cur.fetchall()

        result = []
        for doc in documents:
            cur.execute(
                """
                SELECT data, created_at
                FROM memory_rows
                WHERE document_id = %s
                ORDER BY created_at ASC;
                """,
                (doc["id"],),
            )
            rows = cur.fetchall()
            result.append({
                "id": str(doc["id"]),
                "key": doc["key"],
                "name": doc["name"],
                "description": doc["description"],
                "created_at": doc["created_at"].isoformat(),
                "rows": [
                    {**r["data"], "created_at": r["created_at"].isoformat()}
                    for r in rows
                ],
            })
        return result
