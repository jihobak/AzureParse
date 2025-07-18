import hashlib
import asyncio
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from ..ingestion.di_extract import extract_pdf_content
from .azure_services import get_azure_service_manager
import logging

logger = logging.getLogger(__name__)

class EnhancedDocumentProcessor:
    """
    Enhanced document processor that combines Azure Document Intelligence extraction
    with intelligent chunking and indexing capabilities.
    """
    
    def __init__(self):
        self.chunk_size = 1000
        self.chunk_overlap = 200

    async def process_document(self, file_path: str, filename: str, status_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Process a document from start to finish: extract content, create chunks, and index
        
        Args:
            file_path: Path to the document file
            filename: Original filename
            status_callback: Optional callback function for status updates
            
        Returns:
            Dict containing processing results with chunks and metadata
        """
        processing_start_time = time.time()

        def update_status(step: str, message: str, progress: int = 0):
            """Helper to update status and log with better error handling"""
            # Truncate long messages for logging
            log_message = message[:100] + "..." if len(message) > 100 else message
            logger.info(f"[{filename}] {step}: {log_message} ({progress}%)")
            
            if status_callback:
                try:
                    status_callback({
                        "step": step,
                        "message": message,
                        "progress": progress,
                        "filename": filename
                    })
                except Exception as callback_error:
                    logger.error(f"[{filename}] Status callback error: {str(callback_error)}")

        try:
            file_path_obj = Path(file_path)
            file_size = file_path_obj.stat().st_size

            update_status("VALIDATION", f"✅ File validated: {filename} ({file_size:,} bytes)", 5)
            await asyncio.sleep(0.1)  # Allow UI to update
            
            # Determine file type and use appropriate extraction method
            file_extension = file_path_obj.suffix.lower()
            
            update_status("EXTRACTION", f"🔍 Starting {file_extension.upper()} analysis with Document Intelligence", 10)
            await asyncio.sleep(0.1)
            
            # Quick feedback that extraction is proceeding
            update_status("EXTRACTION", "📊 Connecting to Azure Document Intelligence service...", 12)
            await asyncio.sleep(0.2)

            try:
                if file_extension == '.pdf':
                    doc_result = await extract_pdf_content(file_path_obj)
                # elif file_extension in ['.html', '.htm']:
                #     from ..ingestion.di_extract import extract_html_content
                #     doc_result = await extract_html_content(file_path_obj)
                else:
                    raise Exception(f"Unsupported file type: {file_extension}")
            except Exception as extraction_error:
                error_msg = f"Content extraction failed: {str(extraction_error)}"
                logger.error(f"[{filename}] {error_msg}")
                update_status("EXTRACTION", error_msg, 0)
                raise Exception(error_msg)

            # Check extraction results
            content = doc_result.get("content", "")
            if not content or "Error" in content:
                error_msg = f"No valid content extracted from document"
                logger.error(f"[{filename}] {error_msg}")
                update_status("EXTRACTION", error_msg, 0)
                raise Exception(error_msg)

            content_length = len(content)
            update_status("EXTRACTION", f"Content extracted successfully ({content_length:,} characters)", 25)
            await asyncio.sleep(0.1)
            
            # Extract metadata with enhanced logging
            # 이 부분 스킵

            # Create intelligent chunks
            update_status("CHUNKING", "Creating intelligent document chunks", 50)
            await asyncio.sleep(0.1)

            try:
                chunks = self._create_intelligent_chunks(doc_result, filename)
                if not chunks:
                    logger.warning(f"[{filename}] No chunks created from document")
                    update_status("CHUNKING", "No chunks created - document may be too short", 60)
                else:
                    update_status("CHUNKING", f"Generated {len(chunks)} chunks", 60)
                    logger.info(f"[{filename}] Chunk statistics: {self._get_chunk_statistics(chunks)}")
                    await asyncio.sleep(0.1)

            except Exception as chunking_error:
                logger.error(f"[{filename}] Chunking failed: {str(chunking_error)}")
                chunks = []
                update_status("CHUNKING", f"Chunking failed: {str(chunking_error)}", 60)

            processing_time = time.time() - processing_start_time

            # Prepare comprehensive response
            result = {
                "chunks": chunks,
                "metadata": {
                    "filename": filename,
                    "total_chunks": len(chunks),
                    "content_length": content_length,
                    "file_size": file_size,
                    "processing_time_seconds": round(processing_time, 2),
                    "extraction_metadata": doc_result.get("document_metadata", {}),
                    "structure_info": doc_result.get("structure_info", {})
                },
                "status": "success"
            }
            update_status("COMPLETED", f"Processing completed in {processing_time:.2f}s", 100)
            logger.info(f"[{filename}] Successfully processed: {len(chunks)} chunks")
            
            return result
        
        except Exception as e:
            error_msg = str(e)
            processing_time = time.time() - processing_start_time
            logger.error(f"[{filename}] Error processing document after {processing_time:.2f}s: {error_msg}")
            update_status("ERROR", f"Processing failed: {error_msg}", 0)
            raise Exception(f"Document processing failed: {error_msg}")

    def _create_chunks(self, doc_result: Dict[str, Any], filename: str) -> List[Dict[str, Any]]:
        """
        Create semantic chunks from document content
        """
        content = doc_result.get("content", "")
        if not content:
            return []
        
        chunks = []
        
        # Split content into paragraphs first
        paragraphs = content.split('\n\n')
        current_chunk = ""
        chunk_index = 0
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
                
            # If adding this paragraph would exceed chunk size, finalize current chunk
            if len(current_chunk) + len(paragraph) > self.chunk_size and current_chunk:
                chunk = self._create_chunk_dict(
                    current_chunk, filename, chunk_index
                )
                chunks.append(chunk)
                chunk_index += 1
                
                # Start new chunk with overlap
                overlap_words = current_chunk.split()[-self.chunk_overlap//10:]  # Rough word overlap
                current_chunk = " ".join(overlap_words) + " " + paragraph
            else:
                current_chunk += (" " + paragraph if current_chunk else paragraph)
        
        # Add final chunk if there's remaining content
        if current_chunk.strip():
            chunk = self._create_chunk_dict(
                current_chunk, filename, chunk_index
            )
            chunks.append(chunk)
        
        return chunks

    def _create_chunk_dict(self, content: str, filename: str, index: int) -> Dict[str, Any]:
        """
        Create a standardized chunk dictionary
        """
        # Create unique chunk ID
        chunk_id = hashlib.md5(f"{filename}_{index}_{content[:100]}".encode()).hexdigest()
        
        return {
            "id": chunk_id,
            "content": content.strip(),
            "source": filename,
            "chunk_index": index,
            "chunk_id": chunk_id
        }
    
    def _create_intelligent_chunks(self, doc_result: Dict[str, Any], filename: str) -> List[Dict[str, Any]]:
        """
        Create intelligent chunks using document structure awareness
        """
        try:
            # Use enhanced chunking if paragraphs are available
            paragraphs = doc_result.get("paragraphs", [])
            if paragraphs:
                return self._create_structure_aware_chunks(doc_result, filename)
            else:
                # Fallback to traditional chunking
                return self._create_chunks(doc_result, filename)
                
        except Exception as e:
            logger.error(f"Error creating intelligent chunks for {filename}: {str(e)}")
            # Fallback to basic chunking
            return self._create_chunks(doc_result, filename)


    def _create_structure_aware_chunks(self, doc_result: Dict[str, Any], filename: str) -> List[Dict[str, Any]]:
        """
        Create chunks that respect document structure (paragraphs, sections)
        """
        paragraphs = doc_result.get("paragraphs", [])
        chunks = []
        current_chunk_content = ""
        current_chunk_paragraphs = []
        chunk_index = 0
        
        for paragraph in paragraphs:
            para_content = paragraph.get("content", "").strip()
            para_role = paragraph.get("role", "paragraph")
            
            if not para_content:
                continue
            
            # Check if this paragraph would make the chunk too large
            if (len(current_chunk_content) + len(para_content) > self.chunk_size and 
                current_chunk_content):
                
                # Finalize current chunk
                chunk = self._create_enhanced_chunk_dict(
                    current_chunk_content, filename, chunk_index,
                    structure_info={
                        "paragraph_count": len(current_chunk_paragraphs),
                        "roles": list(set(p.get("role", "paragraph") for p in current_chunk_paragraphs))
                    }
                )
                chunks.append(chunk)
                chunk_index += 1
                
                # Start new chunk with potential overlap
                if para_role in ["title", "sectionHeading"]:
                    # Start fresh for headers
                    current_chunk_content = para_content
                    current_chunk_paragraphs = [paragraph]
                else:
                    # Include overlap from previous chunk
                    overlap_paras = current_chunk_paragraphs[-2:] if len(current_chunk_paragraphs) >= 2 else current_chunk_paragraphs
                    overlap_content = " ".join(p.get("content", "") for p in overlap_paras)
                    current_chunk_content = overlap_content + " " + para_content
                    current_chunk_paragraphs = overlap_paras + [paragraph]

                    # 내가 추가
                    current_chunk_paragraphs = current_chunk_paragraphs[-2:] ##

            else:
                # Add to current chunk
                if current_chunk_content:
                    current_chunk_content += " " + para_content
                else:
                    current_chunk_content = para_content
                current_chunk_paragraphs.append(paragraph)
        
        # Add final chunk if there's remaining content
        if current_chunk_content.strip():
            chunk = self._create_enhanced_chunk_dict(
                current_chunk_content, filename, chunk_index,
                structure_info={
                    "paragraph_count": len(current_chunk_paragraphs),
                    "roles": list(set(p.get("role", "paragraph") for p in current_chunk_paragraphs))
                }
            )
            chunks.append(chunk)
        
        logger.info(f"[{filename}] Structure-aware chunking: {len(paragraphs)} paragraphs → {len(chunks)} chunks")
        return chunks

    def _create_enhanced_chunk_dict(self, content: str, filename: str, index: int, structure_info: Dict = None) -> Dict[str, Any]:
        """
        Create an enhanced chunk dictionary with additional metadata
        """
        # Create unique chunk ID
        chunk_id = hashlib.md5(f"{filename}_{index}_{content[:100]}".encode()).hexdigest()
        
        chunk_data = {
            "id": chunk_id,
            "content": content.strip(),
            "source": filename,
            "chunk_index": index,
            "chunk_id": chunk_id,
            "content_length": len(content),
            "word_count": len(content.split()),
        }
        
        # Add structure information if available
        if structure_info:
            chunk_data.update({
                "structure_info": structure_info,
                "has_structured_content": True
            })
        
        return chunk_data


    def _get_chunk_statistics(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate statistics about the created chunks
        """
        if not chunks:
            return {"total_chunks": 0}
        
        content_lengths = [len(chunk.get("content", "")) for chunk in chunks]
        word_counts = [len(chunk.get("content", "").split()) for chunk in chunks]
        
        return {
            "total_chunks": len(chunks),
            "avg_content_length": sum(content_lengths) / len(content_lengths),
            "min_content_length": min(content_lengths),
            "max_content_length": max(content_lengths),
            "avg_word_count": sum(word_counts) / len(word_counts),
            "total_words": sum(word_counts),
            "has_structure_info": any(chunk.get("structure_info") for chunk in chunks)
        }    