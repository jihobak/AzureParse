"""
Document Parsing API endpoints.
"""
import asyncio
import logging
import os
import tempfile
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from ..core.config import Settings
from ..models.schemas import (
    DocumentUploadBatchResponse,
    DocumentProcessingStatus,
    ProcessingResult,
    BatchProcessingStatus
)
from ..services.document_intelligence_service import DocumentIntelligenceService

logger = logging.getLogger(__name__)

router = APIRouter()

# Global service instance
document_service: Optional[DocumentIntelligenceService] = None

def get_document_service():
    """Get or create document intelligence service instance."""
    global document_service
    if document_service is None:
        settings = Settings()
        document_service = DocumentIntelligenceService(settings)
    return document_service


@router.post("/parsing", response_model=DocumentUploadBatchResponse)
async def parse_documents(
    files: List[UploadFile] = File(...),
    batch_processing: bool = Form(True),
    service: DocumentIntelligenceService = Depends(get_document_service)
):
    """
    """
    try:
        # Validate file types
        supported_types = ["application/pdf", "text/html", "application/msword", 
                          "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
        
        uploaded_files = []
        file_paths = []
        
        for file in files:
            # Validate file type
            if file.content_type not in supported_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {file.content_type}. Supported types: PDF, HTML, Word documents"
                )
            
            # Validate file sieze (50MB limit)
            file_content = await file.read()
            if len(file_content) > 50 * 1024 * 1024:  # 50MB
                raise HTTPException(
                    status_code=413,
                    detail=f"File {file.filename} is too large. Maximum size is 50MB."
                )

            # Save file temporarily
            temp_dir = tempfile.gettempdir()
            temp_file_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{file.filename}")

            with open(temp_file_path, "wb") as temp_file:
                temp_file.write(file_content)
            
            uploaded_files.append(file.filename)
            file_paths.append(temp_file_path)
        
        logger.info(f"Uploaded {len(uploaded_files)} files for processing")

        if batch_processing:
            # Process in batch
            batch_status = await service.process_batch(file_paths, uploaded_files)

            # Clean up temporary files
            for file_path in file_paths:
                try:
                    os.unlink(file_path)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {file_path}: {str(e)}")
            
            return DocumentUploadBatchResponse(
                processing_ids=[result.processing_id for result in batch_status.results],
                results=batch_status.results,
                batch_id=batch_status.batch_id,
                message=f"Batch processing started for {len(uploaded_files)} documents"
            )
        else:
            # Process individually
            processing_ids = []
            results = []
            for file_path, filename in zip(file_paths, uploaded_files):
                result = await service.process_document(file_path, filename)
                processing_ids.append(result.processing_id)
                results.append(result)
            
            # Clean up temporary files
            for file_path in file_paths:
                try:
                    os.unlink(file_path)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {file_path}: {e}")

            return DocumentUploadBatchResponse(
                processing_ids=processing_ids,
                results=results,
                message=f"Processing started for {len(uploaded_files)} documents"
            )            

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error uploading documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
