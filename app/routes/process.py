from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.schemas.memory import ProcessResponse
from app.services.processor import (
    MemoryNotFoundError,
    MemoryProcessingError,
    process_memory as run_memory_processing,
)


router = APIRouter()


@router.post("/process/{memory_id}", response_model=ProcessResponse)
def process_memory(memory_id: UUID):
    try:
        result = run_memory_processing(memory_id)
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Memory not found") from exc
    except MemoryProcessingError as exc:
        raise HTTPException(status_code=500, detail="Processing failed") from exc

    return ProcessResponse(
        status="processed",
        memoryId=memory_id,
        processingStatus=result["processing_status"],
        visualDescription=result["visual_description"],
        extractedText=result["extracted_text"],
        detectedComponents=result["detected_components"],
        detectedColors=result["detected_colors"],
        autoTags=result["auto_tags"],
    )
