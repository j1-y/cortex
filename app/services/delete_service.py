from typing import Any
from uuid import UUID

from app.database import get_connection


def delete_bookmark_memories(nyabag_bookmark_id: UUID, user_id: UUID) -> dict[str, Any]:
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM cortex_memories
                WHERE nyabag_bookmark_id = %s
                  AND user_id = %s
                """,
                (nyabag_bookmark_id, user_id),
            )
            memory_ids = [str(row[0]) for row in cur.fetchall()]

            if not memory_ids:
                conn.commit()
                return {
                    "deleted_memories": 0,
                    "deleted_embeddings": 0,
                }

            cur.execute(
                """
                DELETE FROM cortex_embeddings
                WHERE memory_id = ANY(%s::uuid[])
                """,
                (memory_ids,),
            )
            deleted_embeddings = cur.rowcount

            cur.execute(
                """
                DELETE FROM cortex_memories
                WHERE id = ANY(%s::uuid[])
                  AND nyabag_bookmark_id = %s
                  AND user_id = %s
                """,
                (memory_ids, nyabag_bookmark_id, user_id),
            )
            deleted_memories = cur.rowcount

        conn.commit()

        return {
            "deleted_memories": deleted_memories,
            "deleted_embeddings": deleted_embeddings,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
