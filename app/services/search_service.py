from typing import Any

from app.database import get_connection
from app.services.embeddings import (
    EMBEDDING_MODEL,
    format_vector_for_pgvector,
    generate_text_embedding,
)


DEFAULT_SEARCH_LIMIT = 10
MIN_SEARCH_LIMIT = 1
MAX_SEARCH_LIMIT = 50
EMBEDDING_TYPE = "memory_analysis"
PREVIEW_CHARS = 300


class EmptySearchQueryError(ValueError):
    pass


def search_memories(query: str, limit: int = DEFAULT_SEARCH_LIMIT) -> dict[str, Any]:
    normalized_query = query.strip()
    if not normalized_query:
        raise EmptySearchQueryError("Search query cannot be empty")

    normalized_limit = clamp_limit(limit)
    query_embedding = generate_text_embedding(normalized_query)
    query_vector = format_vector_for_pgvector(query_embedding)

    conn = get_connection()
    try:
        embedding_columns = get_table_columns(conn, "cortex_embeddings")
        model_name_select = (
            "e.model_name"
            if "model_name" in embedding_columns
            else "%s"
        )
        params: list[Any] = []
        if "model_name" not in embedding_columns:
            params.append(EMBEDDING_MODEL)

        params.extend([query_vector, query_vector, normalized_limit])

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    m.id AS memory_id,
                    m.nyabag_bookmark_id,
                    m.user_id,
                    m.url,
                    m.title,
                    m.summary,
                    m.screenshot_url,
                    m.visual_description,
                    m.auto_tags,
                    e.id AS embedding_id,
                    e.embedding_type,
                    {model_name_select} AS model_name,
                    e.content,
                    1 - (e.embedding <=> %s::vector) AS similarity
                FROM cortex_embeddings e
                JOIN cortex_memories m ON m.id = e.memory_id
                WHERE e.embedding_type = %s
                  AND m.processing_status = %s
                ORDER BY e.embedding <=> %s::vector
                LIMIT %s
                """,
                build_search_params(params),
            )
            rows = cur.fetchall()

        return {
            "query": normalized_query,
            "count": len(rows),
            "results": [build_search_result(row) for row in rows],
        }
    finally:
        conn.close()


def build_search_params(params: list[Any]) -> list[Any]:
    if len(params) == 3:
        query_vector, order_vector, limit = params
        return [query_vector, EMBEDDING_TYPE, "completed", order_vector, limit]

    model_name, query_vector, order_vector, limit = params
    return [model_name, query_vector, EMBEDDING_TYPE, "completed", order_vector, limit]


def build_search_result(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "memoryId": row[0],
        "nyabagBookmarkId": row[1],
        "userId": row[2],
        "url": row[3],
        "title": row[4],
        "summary": row[5],
        "screenshotUrl": row[6],
        "visualPreview": preview_text(row[7]),
        "autoTags": row[8] or [],
        "embeddingId": row[9],
        "embeddingType": row[10],
        "modelName": row[11] or EMBEDDING_MODEL,
        "contentPreview": preview_text(row[12]),
        "similarity": round(float(row[13]), 4) if row[13] is not None else 0.0,
    }


def clamp_limit(limit: int) -> int:
    return max(MIN_SEARCH_LIMIT, min(MAX_SEARCH_LIMIT, limit))


def preview_text(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    if len(text) <= PREVIEW_CHARS:
        return text

    return text[:PREVIEW_CHARS].rstrip() + "..."


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
