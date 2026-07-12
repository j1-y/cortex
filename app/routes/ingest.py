import logging

from fastapi import APIRouter, HTTPException

from app.schemas.memory import IngestResponse, RememberRequest
from app.services.ingest_service import (
    IngestCreationError,
    IngestEmbeddingError,
    IngestProcessingError,
    ingest_memory,
)
from app.services.color_extractor import extract_palette


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
def ingest(payload: RememberRequest):
    try:
        result = ingest_memory(payload)
    except IngestProcessingError as exc:
        logger.exception("Ingest failed during processing")
        raise HTTPException(
            status_code=500,
            detail=f"Ingest failed during processing: {str(exc)}",
        ) from exc
    except IngestEmbeddingError as exc:
        logger.exception("Ingest failed during embedding")
        raise HTTPException(
            status_code=500,
            detail=f"Ingest failed during embedding: {str(exc)}",
        ) from exc
    except IngestCreationError as exc:
        logger.exception("Ingest failed during memory creation")
        raise HTTPException(
            status_code=500,
            detail=f"Ingest failed: {str(exc)}",
        ) from exc
    except Exception as exc:
        logger.exception("Ingest failed")
        raise HTTPException(
            status_code=500,
            detail=f"Ingest failed: {type(exc).__name__}: {str(exc)}",
        ) from exc

    # Extract the palette from the incoming screenshot URL
    screenshot_url = str(payload.screenshotUrl) if payload.screenshotUrl else None
    extracted_palette = extract_palette(screenshot_url, color_count=5)

    return IngestResponse(
        status="ingested",
        memoryId=result["memory_id"],
        processingStatus=result["processing_status"],
        embeddingStatus=result["embedding_status"],
        embeddingId=result["embedding_id"],
        modelName=result["model_name"],
        dimensions=result["dimensions"],
        title=result["title"],
        url=result["url"],
        autoTags=result["auto_tags"],
        visualPreview=result["visual_preview"],
        palette=extracted_palette,
    )
