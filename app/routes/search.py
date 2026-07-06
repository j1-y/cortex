import logging

from fastapi import APIRouter, HTTPException, Query

from app.schemas.memory import SearchResponse
from app.services.search_service import EmptySearchQueryError, search_memories


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/search", response_model=SearchResponse)
def search(q: str = Query(...), limit: int = Query(10)):
    try:
        return SearchResponse(**search_memories(q, limit))
    except EmptySearchQueryError as exc:
        raise HTTPException(status_code=400, detail="Search query cannot be empty") from exc
    except Exception as exc:
        logger.exception("Search failed")
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {type(exc).__name__}: {str(exc)}",
        ) from exc
