from typing import List, Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime
from enum import Enum

from langchain.schema import Document
from pydantic import BaseModel, Field


class DocumentProcessingStatus(BaseModel):
    """Status of document processing."""
    id: str = Field(..., description="Unique processing ID")
    filename: str = Field(..., description="Name of the file being processed")
    status: str = Field(..., description="Processing status: processing, extracting, chunking, embedding, completed, failed")
    progress: int = Field(default=0, description="Progress percentage (0-100)")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    message: str = Field(default="", description="Status message")
    error: Optional[str] = None


class ProcessingResult(BaseModel):
    """Result of document processing."""
    processing_id: str = Field(..., description="Unique processing ID")
    filename: str = Field(..., description="Name of the processed file")
    status: str = Field(..., description="Final processing status")
    chunks_created: int = Field(default=0, description="Number of chunks created")
    characters_processed: int = Field(default=0, description="Number of characters processed")
    processing_time_seconds: float = Field(default=0.0, description="Processing time in seconds")
    chunks: List[Optional[Document]] = Field(default_factory=list, description="List of processed document chunks")
    error: Optional[str] = None


class BatchProcessingStatus(BaseModel):
    """Status of batch processing."""
    batch_id: str = Field(..., description="Unique batch ID")
    total_documents: int = Field(..., description="Total number of documents in batch")
    completed_documents: int = Field(default=0, description="Number of completed documents")
    failed_documents: int = Field(default=0, description="Number of failed documents")
    processing_documents: int = Field(default=0, description="Number of documents currently processing")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    status: str = Field(default="processing", description="Overall batch status")
    results: List[ProcessingResult] = Field(default_factory=list)


class DocumentUploadBatchResponse(BaseModel):
    """Response for document upload batch."""
    processing_ids: List[str] = Field(..., description="List of processing IDs")
    batch_id: Optional[str] = None
    message: str = Field(default="Documents uploaded successfully")
    results: List[ProcessingResult] = Field(default_factory=list, description="Results of each document processing")
