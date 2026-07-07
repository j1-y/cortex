import logging
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query

from app.auth import require_internal_api_key
from app.schemas.memory import DeleteBookmarkMemoryResponse
from app.services.delete_service import delete_bookmark_memories


logger = logging.getLogger(__name__)
router = APIRouter()


@router.delete("/memories/bookmark/{nyabag_bookmark_id}", response_model=DeleteBookmarkMemoryResponse)
def delete_bookmark_memory(
    nyabag_bookmark_id: UUID,
    user_id: UUID = Query(..., alias="userId"),
    authorization: str | None = Header(default=None),
):
    require_internal_api_key(authorization)

    try:
        result = delete_bookmark_memories(nyabag_bookmark_id, user_id)
    except Exception as exc:
        logger.exception("Bookmark memory delete failed")
        raise HTTPException(
            status_code=500,
            detail=f"Bookmark memory delete failed: {type(exc).__name__}: {str(exc)}",
        ) from exc

    return DeleteBookmarkMemoryResponse(
        deletedMemories=result["deleted_memories"],
        deletedEmbeddings=result["deleted_embeddings"],
    )
