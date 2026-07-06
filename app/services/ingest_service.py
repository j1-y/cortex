from typing import Any

from app.schemas.memory import RememberRequest
from app.services.embedding_processor import embed_memory
from app.services.memory_service import create_memory
from app.services.processor import process_memory


class IngestProcessingError(Exception):
    pass


class IngestEmbeddingError(Exception):
    pass


class IngestCreationError(Exception):
    pass


def ingest_memory(payload: RememberRequest) -> dict[str, Any]:
    # TODO: Move processing and embedding into background workers/queue before production.
    try:
        created_memory = create_memory(payload)
    except Exception as exc:
        raise IngestCreationError(f"{type(exc).__name__}: {str(exc)}") from exc

    memory_id = created_memory["memory_id"]

    try:
        processing_result = process_memory(memory_id)
    except Exception as exc:
        raise IngestProcessingError(f"{type(exc).__name__}: {str(exc)}") from exc

    try:
        embedding_result = embed_memory(memory_id)
    except Exception as exc:
        raise IngestEmbeddingError(f"{type(exc).__name__}: {str(exc)}") from exc

    return {
        "memory_id": memory_id,
        "processing_status": processing_result["processing_status"],
        "embedding_id": embedding_result["embedding_id"],
        "embedding_status": "embedded",
        "model_name": embedding_result["model_name"],
        "dimensions": embedding_result["dimensions"],
        "title": payload.title,
        "url": str(payload.url),
        "auto_tags": processing_result.get("auto_tags", []),
        "visual_preview": preview_text(processing_result.get("visual_description")),
    }


def preview_text(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    if len(text) <= 300:
        return text

    return text[:300].rstrip() + "..."
