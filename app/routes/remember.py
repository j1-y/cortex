from fastapi import APIRouter, HTTPException
from psycopg import Error as PsycopgError

from app.schemas.memory import RememberRequest, RememberResponse
from app.services.memory_service import create_memory


router = APIRouter()


@router.post("/remember", response_model=RememberResponse)
def remember_memory(payload: RememberRequest):
    try:
        created_memory = create_memory(payload)

        return RememberResponse(
            status="queued",
            memoryId=created_memory["memory_id"],
            processingStatus=created_memory["processing_status"],
        )
    except PsycopgError as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not store memory.",
        ) from exc
