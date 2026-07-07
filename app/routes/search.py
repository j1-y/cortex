import logging
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query

from app.auth import require_internal_api_key
from app.schemas.memory import SearchResponse
from app.services.search_service import EmptySearchQueryError, search_memories


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(...),
    limit: int = Query(10),
    user_id: UUID = Query(..., alias="userId"),
    authorization: str | None = Header(default=None),
):
    require_internal_api_key(authorization)

    try:
        return SearchResponse(**search_memories(q, user_id, limit))
    except EmptySearchQueryError as exc:
        raise HTTPException(status_code=400, detail="Search query cannot be empty") from exc
    except Exception as exc:
        logger.exception("Search failed")
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {type(exc).__name__}: {str(exc)}",
        ) from exc
