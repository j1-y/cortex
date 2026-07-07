import hmac
import logging
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query

from app.config import CORTEX_INTERNAL_API_KEY
from app.schemas.memory import DeleteBookmarkMemoryResponse
from app.services.delete_service import delete_bookmark_memories


logger = logging.getLogger(__name__)
router = APIRouter()


def require_internal_api_key(authorization: str | None) -> None:
    if not CORTEX_INTERNAL_API_KEY:
        raise HTTPException(status_code=503, detail="Internal Cortex API key is not configured")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    if not hmac.compare_digest(token, CORTEX_INTERNAL_API_KEY):
        raise HTTPException(status_code=403, detail="Invalid bearer token")


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
