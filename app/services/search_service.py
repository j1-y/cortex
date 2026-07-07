import re
from typing import Any
from uuid import UUID

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
SEARCH_VECTOR_FLOOR = 0.35
CANDIDATE_MULTIPLIER = 5
MAX_CANDIDATE_LIMIT = 100
GENERIC_QUERY_TERMS = {
    "a",
    "an",
    "and",
    "app",
    "apps",
    "clean",
    "design",
    "designs",
    "for",
    "home",
    "homepage",
    "interface",
    "interfaces",
    "landing",
    "layout",
    "layouts",
    "modern",
    "of",
    "page",
    "pages",
    "product",
    "products",
    "screen",
    "screens",
    "site",
    "sites",
    "the",
    "ui",
    "ux",
    "visual",
    "visuals",
    "web",
    "website",
    "websites",
    "with",
}
TERM_SYNONYMS = {
    "globe": {"globe", "earth", "world", "global", "planet", "map"},
    "earth": {"earth", "globe", "world", "global", "planet", "map"},
    "world": {"world", "earth", "globe", "global", "planet", "map"},
    "global": {"global", "world", "earth", "globe", "planet", "map"},
    "map": {"map", "maps", "earth", "globe", "world", "global", "geographic"},
}


class EmptySearchQueryError(ValueError):
    pass


def search_memories(query: str, user_id: UUID, limit: int = DEFAULT_SEARCH_LIMIT) -> dict[str, Any]:
    normalized_query = query.strip()
    if not normalized_query:
        raise EmptySearchQueryError("Search query cannot be empty")

    normalized_limit = clamp_limit(limit)
    candidate_limit = get_candidate_limit(normalized_limit)
    specific_term_groups = get_specific_query_term_groups(normalized_query)
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

        params.extend([
            query_vector,
            EMBEDDING_TYPE,
            "completed",
            user_id,
            query_vector,
            candidate_limit,
        ])

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
                    m.extracted_text,
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
                  AND m.user_id = %s
                ORDER BY e.embedding <=> %s::vector
                LIMIT %s
                """,
                params,
            )
            rows = cur.fetchall()

        candidates = [build_search_candidate(row) for row in rows]
        filtered_results = filter_and_rank_results(candidates, specific_term_groups)
        results = [build_public_search_result(result) for result in filtered_results[:normalized_limit]]

        return {
            "query": normalized_query,
            "count": len(results),
            "results": results,
        }
    finally:
        conn.close()


def build_search_candidate(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "memoryId": row[0],
        "nyabagBookmarkId": row[1],
        "userId": row[2],
        "url": row[3],
        "title": row[4],
        "summary": row[5],
        "screenshotUrl": row[6],
        "visualPreview": preview_text(row[7]),
        "autoTags": row[9] or [],
        "embeddingId": row[10],
        "embeddingType": row[11],
        "modelName": row[12] or EMBEDDING_MODEL,
        "contentPreview": preview_text(row[13]),
        "similarity": round(float(row[14]), 4) if row[14] is not None else 0.0,
        "_evidenceText": build_evidence_text(row),
    }


def build_public_search_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "memoryId": result["memoryId"],
        "nyabagBookmarkId": result["nyabagBookmarkId"],
        "userId": result["userId"],
        "url": result["url"],
        "title": result["title"],
        "summary": result["summary"],
        "screenshotUrl": result["screenshotUrl"],
        "visualPreview": result["visualPreview"],
        "autoTags": result["autoTags"],
        "embeddingId": result["embeddingId"],
        "embeddingType": result["embeddingType"],
        "modelName": result["modelName"],
        "contentPreview": result["contentPreview"],
        "similarity": result["similarity"],
    }


def filter_and_rank_results(
    candidates: list[dict[str, Any]],
    specific_term_groups: list[set[str]],
) -> list[dict[str, Any]]:
    filtered = [
        candidate
        for candidate in candidates
        if candidate["similarity"] >= SEARCH_VECTOR_FLOOR
        and has_required_evidence(candidate, specific_term_groups)
    ]

    return sorted(
        filtered,
        key=lambda candidate: (
            evidence_match_count(candidate["_evidenceText"], specific_term_groups),
            candidate["similarity"],
        ),
        reverse=True,
    )


def has_required_evidence(candidate: dict[str, Any], specific_term_groups: list[set[str]]) -> bool:
    if not specific_term_groups:
        return True

    evidence_text = candidate["_evidenceText"]
    return all(matches_any_term(evidence_text, term_group) for term_group in specific_term_groups)


def evidence_match_count(evidence_text: str, specific_term_groups: list[set[str]]) -> int:
    return sum(1 for term_group in specific_term_groups if matches_any_term(evidence_text, term_group))


def matches_any_term(text: str, terms: set[str]) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", text) for term in terms)


def get_specific_query_term_groups(query: str) -> list[set[str]]:
    groups = []
    seen = set()
    for token in tokenize_query(query):
        if token in GENERIC_QUERY_TERMS or token in seen:
            continue
        seen.add(token)
        groups.append(expand_query_term(token))

    return groups


def expand_query_term(term: str) -> set[str]:
    terms = set(TERM_SYNONYMS.get(term, {term}))
    if len(term) > 3 and not term.endswith("s"):
        terms.add(f"{term}s")
    if len(term) > 3 and term.endswith("s"):
        terms.add(term.rstrip("s"))
    return terms


def tokenize_query(query: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", query.lower())


def build_evidence_text(row: tuple[Any, ...]) -> str:
    evidence_parts = [
        row[4],
        row[5],
        row[7],
        row[8],
        " ".join(row[9] or []),
        row[13],
    ]
    return " ".join(str(part or "") for part in evidence_parts).lower()


def get_candidate_limit(limit: int) -> int:
    return min(MAX_CANDIDATE_LIMIT, max(limit, limit * CANDIDATE_MULTIPLIER))


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
