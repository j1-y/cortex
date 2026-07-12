from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, HttpUrl


class RememberRequest(BaseModel):
    nyabagBookmarkId: UUID
    userId: UUID
    url: HttpUrl
    title: Optional[str] = None
    summary: Optional[str] = None
    screenshotUrl: Optional[HttpUrl] = None


class RememberResponse(BaseModel):
    status: str
    memoryId: UUID
    processingStatus: str


class ProcessResponse(BaseModel):
    status: str
    memoryId: UUID
    processingStatus: str
    visualDescription: Optional[str] = None
    extractedText: Optional[str] = None
    detectedComponents: list[dict[str, Any]]
    detectedColors: list[dict[str, Any]]
    autoTags: list[str]


class EmbedResponse(BaseModel):
    status: str
    memoryId: UUID
    embeddingId: UUID
    embeddingType: str
    modelName: str
    dimensions: int
    contentPreview: str


class SearchResult(BaseModel):
    memoryId: UUID
    nyabagBookmarkId: UUID
    userId: UUID
    title: Optional[str] = None
    url: str
    summary: Optional[str] = None
    screenshotUrl: Optional[str] = None
    similarity: float
    autoTags: list[str]
    visualPreview: Optional[str] = None
    contentPreview: Optional[str] = None
    embeddingId: UUID
    embeddingType: str
    modelName: str


class SearchResponse(BaseModel):
    query: str
    count: int
    results: list[SearchResult]


class IngestResponse(BaseModel):
    status: str
    memoryId: UUID
    processingStatus: str
    embeddingStatus: str
    embeddingId: UUID
    modelName: str
    dimensions: int
    title: Optional[str] = None
    url: str
    autoTags: list[str]
    visualPreview: Optional[str] = None
    palette: list[str] = []


class DeleteBookmarkMemoryResponse(BaseModel):
    deletedMemories: int
    deletedEmbeddings: int
