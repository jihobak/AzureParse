import logging
from pathlib import Path
import time
from typing import Any, Dict
from fastapi import APIRouter

from ..services.enhanced_document_processor import EnhancedDocumentProcessor


logger = logging.getLogger(__name__)

router = APIRouter()

class ModularProcessor:
    """Simple modular processor with granular steps"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def process_document_with_steps(self, file_path: str, filename: str, status_callback=None):
        """Process document with granular steps and status updates."""
        
        start_time = time.time()

        try:
            self.logger.info(f"[{filename}] Starting modular processing.")

            # Step 1: File Validation (0-15%)
            await self._update_status(status_callback, "VALIDATION", "Validating file format and size...", 5)
            file_info = await self.__validate_file(file_path)
            await self._update_status(status_callback, "VALIDATION", f"File validated: {file_info['size_mb']:.1f}MB", 15)

            # Step 2: Document Processing (15-100%)
            await self._update_status(status_callback, "EXTRACTION", "Starting content extraction with Document Intelligence...", 20)

            self.logger.info(f"[{filename}] Calling enhanced processor")

            # Create a simple passthrough callback that maps progress
            def progress_callback(status_update):
                try:
                    step = status_update.get("step", "PROCESSING")
                    message = status_update.get("message", "")
                    base_progress = status_update.get("progress", 0)

                    # Map the processor's 0-100% to our 20-100% range
                    mapped_progress = 20 + (base_progress * 0.8)

                    self.logger.info(
                        f"[{filename}] Progress update: {step} - {message} ({mapped_progress:.0f}%)"
                    )

                    if status_callback:
                        status_callback({
                            "step": step,
                            "message": message,
                            "progress": int(mapped_progress)
                        })
                except Exception as e:
                    self.logger.error(f"[{filename}] Error in progress callback: {e}")

            # Try with enhanced processor first, fall back if it fails
            try:
                processor = EnhancedDocumentProcessor()
                result = await processor.process_document(
                    file_path,
                    filename,
                    progress_callback
                )
            except Exception as enhanced_error:
                self.logger.error(f"[{filename}] Enhanced processor failed: {enhanced_error}")
                # await self._update_status(status_callback, "EXTRACTION", "Document Intelligence failed, using basic extraction...", 40)
                raise enhanced_error

            # Final status
            processing_time = time.time() - start_time
            await self._update_status(status_callback, "COMPLETED", f"Processing completed in {processing_time:.1f}s: 100")

            self.logger.info(f"[{filename}] Modular processing completed successfully")

            return result
        
        except Exception as e:
            error_msg = f"Processing failed: {str(e)}"
            processing_time = time.time() - start_time
            self.logger.error(f"[{filename}] Error in modular processing after {processing_time:.2f}s: {error_msg}")
            await self._update_status(status_callback, "ERROR", error_msg, 0)
            raise e
    
    async def _update_status(self, callback, step: str, message: str, progress: int):
        """Update processing status with error handling."""
        self.logger.info(f"[MODULAR] {step}: {message} ({progress}%)")

        if callback:
            try:
                callback({
                    "step": step,
                    "message": message,
                    "progress": progress
                })
            except Exception as e:
                self.logger.error(f"Status callback error: {e}")
    
    async def __validate_file(self, file_path: str) -> Dict[str, Any]:
        """Validate file and return info"""
        try:
            file_obj = Path(file_path)
            if not file_obj.exists():
                raise FileNotFoundError(f"File {file_path} does not exist.")

            file_size = file_obj.stat().st_size
            if file_size == 0:
                raise ValueError("File is empty.")  
            
            self.logger.info(f"File {file_path} validated successful: {file_size} bytes.")

            return {
                "size_bytes": file_size,
                "size_mb": file_size / (1024 * 1024),
                "extension": file_obj.suffix.lower(),
            }
        except Exception as e:
            self.logger.error(f"File validation failed: {e}")
            raise e
    
    async def _fallback_processing(self, file_path: str, filename: str, status_callback=None):
        pass