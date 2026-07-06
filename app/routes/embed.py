import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.schemas.memory import EmbedResponse
from app.services.embedding_processor import (
    MemoryNotCompletedError,
    MemoryNotFoundError,
    embed_memory as run_memory_embedding,
)


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/embed/{memory_id}", response_model=EmbedResponse)
def embed_memory(memory_id: UUID):
    try:
        result = run_memory_embedding(memory_id)
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Memory not found") from exc
    except MemoryNotCompletedError as exc:
        raise HTTPException(
            status_code=400,
            detail="Memory must be completed before embedding",
        ) from exc
    except Exception as e:
        logger.exception("Embedding failed")
        raise HTTPException(
            status_code=500,
            detail=f"Embedding failed: {type(e).__name__}: {str(e)}",
        ) from e

    return EmbedResponse(
        status="embedded",
        memoryId=result["memory_id"],
        embeddingId=result["embedding_id"],
        embeddingType=result["embedding_type"],
        modelName=result["model_name"],
        dimensions=result["dimensions"],
        contentPreview=result["content_preview"],
    )
