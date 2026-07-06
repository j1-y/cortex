from typing import Any

from app.database import get_connection
from app.schemas.memory import RememberRequest


def create_memory(payload: RememberRequest) -> dict[str, Any]:
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cortex_memories (
                    nyabag_bookmark_id,
                    user_id,
                    url,
                    title,
                    summary,
                    screenshot_url,
                    processing_status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, processing_status
                """,
                (
                    payload.nyabagBookmarkId,
                    payload.userId,
                    str(payload.url),
                    payload.title,
                    payload.summary,
                    str(payload.screenshotUrl) if payload.screenshotUrl else None,
                    "pending",
                ),
            )
            memory_id, processing_status = cur.fetchone()

        conn.commit()

        return {
            "memory_id": memory_id,
            "processing_status": processing_status,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
