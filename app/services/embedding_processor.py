import logging
from typing import Any
from uuid import UUID

from app.database import get_connection
from app.services.embeddings import (
    EMBEDDING_MODEL,
    build_memory_embedding_text,
    format_vector_for_pgvector,
    generate_text_embedding,
)


EMBEDDING_TYPE = "memory_analysis"
logger = logging.getLogger(__name__)


class MemoryNotFoundError(Exception):
    pass


class MemoryNotCompletedError(Exception):
    pass


def get_completed_memory(memory_id: UUID) -> dict[str, Any]:
    conn = get_connection()
    try:
        columns = get_cortex_memory_columns(conn)
        optional_columns = [
            column
            for column in ("detected_components", "detected_colors")
            if column in columns
        ]
        selected_columns = [
            "id",
            "nyabag_bookmark_id",
            "user_id",
            "url",
            "title",
            "summary",
            "visual_description",
            "extracted_text",
            "auto_tags",
            "processing_status",
            *optional_columns,
        ]

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {", ".join(selected_columns)}
                FROM cortex_memories
                WHERE id = %s
                """,
                (memory_id,),
            )
            row = cur.fetchone()

        if row is None:
            raise MemoryNotFoundError("Memory not found")

        memory = dict(zip(selected_columns, row))
        memory.setdefault("detected_components", [])
        memory.setdefault("detected_colors", [])

        if memory.get("processing_status") != "completed":
            raise MemoryNotCompletedError("Memory must be completed before embedding")

        return memory
    finally:
        conn.close()


def upsert_memory_embedding(
    memory_id: UUID,
    content: str,
    embedding: list[float],
) -> dict[str, Any]:
    vector = format_vector_for_pgvector(embedding)
    conn = get_connection()

    try:
        embedding_columns = get_table_columns(conn, "cortex_embeddings")
        insert_columns = [
            "memory_id",
            "embedding_type",
            "content",
            "embedding",
        ]
        placeholders = [
            "%s",
            "%s",
            "%s",
            "%s::vector",
        ]
        values: list[Any] = [memory_id, EMBEDDING_TYPE, content, vector]

        if "model_name" in embedding_columns:
            insert_columns.append("model_name")
            placeholders.append("%s")
            values.append(EMBEDDING_MODEL)

        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM cortex_embeddings
                WHERE memory_id = %s
                  AND embedding_type = %s
                """,
                (memory_id, EMBEDDING_TYPE),
            )
            cur.execute(
                f"""
                INSERT INTO cortex_embeddings (
                    {", ".join(insert_columns)}
                )
                VALUES ({", ".join(placeholders)})
                RETURNING id, memory_id, embedding_type, model_name, created_at
                """
                if "model_name" in embedding_columns
                else f"""
                INSERT INTO cortex_embeddings (
                    {", ".join(insert_columns)}
                )
                VALUES ({", ".join(placeholders)})
                RETURNING id, memory_id, embedding_type, created_at
                """,
                values,
            )
            row = cur.fetchone()

        conn.commit()
        model_name = row[3] if "model_name" in embedding_columns else EMBEDDING_MODEL
        created_at = row[4] if "model_name" in embedding_columns else row[3]

        return {
            "embedding_id": row[0],
            "memory_id": row[1],
            "embedding_type": row[2],
            "model_name": model_name,
            "created_at": created_at,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def embed_memory(memory_id: UUID) -> dict[str, Any]:
    memory = get_completed_memory(memory_id)
    content = build_memory_embedding_text(memory)
    embedding = generate_text_embedding(content)
    stored_embedding = upsert_memory_embedding(memory_id, content, embedding)

    return {
        **stored_embedding,
        "content_preview": build_content_preview(content),
        "dimensions": len(embedding),
    }


def get_cortex_memory_columns(conn) -> set[str]:
    return get_table_columns(conn, "cortex_memories")


def get_table_columns(conn, table_name: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s
            """,
            (table_name,),
        )
        return {row[0] for row in cur.fetchall()}


def build_content_preview(content: str) -> str:
    preview = content.strip()
    if len(preview) <= 500:
        return preview

    return preview[:500].rstrip() + "..."
