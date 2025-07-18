from pathlib import Path
from typing import Dict, Any, List
import logging
from ..services.azure_services import get_azure_service_manager

logger = logging.getLogger(__name__)


async def extract_pdf_content(file_path: Path) -> Dict[str, Any]:
    """
    Extract content from PDF using Azure Document Intelligence via centralized service manager
    with enhanced metadata extraction and structure preservation.
    """
    try:
        logger.info(f"Starting Document Intelligence extraction for {file_path.name}")

        # Use the centralized Azure Service Manger which handles both real and mock services
        azure_service = await get_azure_service_manager()

        with open(file_path, "rb") as f:
            file_bytes = f.read()
        
        logger.info(f"File size: {len(file_bytes)} bytes")

        if len(file_bytes) == 0:
            raise Exception("File is empty")
        
        # Use the Azure Service Manager to analyze the document
        try:
            logger.info("Starting Document Intelligence analysis via Azure Service Manager...")
            result = await azure_service.analyze_document(
                document_content=file_bytes,
                content_type="application/pdf",
                filename=file_path.name
            )
            logger.info("Document Intelligence analysis completed successfully")
        except Exception as di_error:
            logger.error(f"Document Intelligence analysis failed: {str(di_error)}")
            raise Exception(f"Document Intelligence service error: {str(di_error)}")
        
        # Validate the result
        if not result or not result.get('content'):
            raise Exception("Document Intelligence returned empty result")
        
        # The Azure Service Manager already returns structured data, but we need to adapt it
        # to the format expected by the enhanced processor
        try:
            extracted_data = _adapt_azure_service_result(result, file_path.name)
        except Exception as extract_error:
            logger.error(f"Error adapting DI result: {extract_error}")
            # Return basic structure with available content
            return {
                "content": result.get('content', ''),
                "pages": [],
                "tables": result.get('tables', []),
                "paragraphs": [],
                "key_value_pairs": result.get('key_value_pairs', {}),
                "document_metadata": {"content_length": len(result.get('content', ''))},
                "structure_info": {}
            }
        
        logger.info(f"Extracted {len(extracted_data.get('pages', []))} pages, "
                   f"{len(extracted_data.get('tables', []))} tables, "
                   f"{len(extracted_data.get('paragraphs', []))} paragraphs")
        
        return extracted_data
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error extracting content from {file_path.name}: {error_msg}")
        
        # Don't return error content, raise exception so fallback can handle it
        raise Exception(f"Document Intelligence extraction failed: {error_msg}")

def _adapt_azure_service_result(result: Dict[str, Any], filename: str) -> Dict[str, Any]:
    """
    Adapt the Azure Service Manager result to the expected format
    """
    try:
        extracted = {
            "content": result.get("content", ""),
            "pages": [],
            "tables": result.get('tables', []),
            "paragraphs": [],
            "key_value_pairs": [],
            "document_metadata": {},
            "structure_info": {}
        }

        # Create basic page structure if not available
        content_length = len(extracted["content"])
        if content_length > 0:
            # Estimate pages based on content length (rough approximation)
            estimated_pages = max(1, content_length // 3000)  # ~3000 chars per page
            for i in range(estimated_pages):
                page_data = {
                    "page_number": i + 1,
                    "width": 612,  # Standard letter size
                    "height": 792,
                    "unit": "pixel",
                    "text_angle": 0,
                    "lines": [],
                    "words": []
                }
                extracted["pages"].append(page_data)
        
        # Convert key_value_pairs from dict to list format
        kv_pairs = result.get('key_value_pairs', {})
        if isinstance(kv_pairs, dict):
            for key, value_data in kv_pairs.items():
                kv_data = {
                    "key": key,
                    "value": value_data.get('value', '') if isinstance(value_data, dict) else str(value_data),
                    "confidence": value_data.get('confidence', 0.0) if isinstance(value_data, dict) else 0.0
                }
                extracted["key_value_pairs"].append(kv_data)

        # Create document metadata
        extracted["document_metadata"] = {
            "page_count": len(extracted["pages"]),
            "table_count": len(extracted["tables"]),
            "paragraph_count": 0,  # Will be estimated below
            "has_tables": len(extracted["tables"]) > 0,
            "has_key_value_pairs": len(extracted["key_value_pairs"]) > 0,
            "content_length": content_length
        }
        
        # Create basic paragraph structure from content
        content = extracted["content"]
        if content:
            paragraphs = content.split('\n\n')  # Split on double newlines
            for i, para_text in enumerate(paragraphs):
                if para_text.strip():
                    para_data = {
                        "content": para_text.strip(),
                        "role": "paragraph",
                        "bounding_regions": [],
                        "paragraph_id": i
                    }
                    extracted["paragraphs"].append(para_data)
            
            extracted["document_metadata"]["paragraph_count"] = len(extracted["paragraphs"])

        # Structure analysis for credibility assessment
        extracted["structure_info"] = _analyze_document_structure(extracted)
        
        return extracted

    except Exception as e:
        logger.error(f"Error adapting Azure service result: {str(e)}")
        # Return minimal structure
        return {
            "content": result.get('content', ''),
            "pages": [{"page_number": 1, "width": 612, "height": 792, "unit": "pixel", "text_angle": 0, "lines": [], "words": []}],
            "tables": [],
            "paragraphs": [],
            "key_value_pairs": [],
            "document_metadata": {"content_length": len(result.get('content', ''))},
            "structure_info": {}
        }

def _analyze_document_structure(extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze document structure for credibility assessment and intelligent processing
    """
    try:
        structure = {
            "document_type": "financial_filing",
            "has_formal_structure": False,
            "section_headers": [],
            "credibility_indicators": {
                "has_tables": len(extracted_data.get("tables", [])) > 0,
                "has_structured_content": len(extracted_data.get("paragraphs", [])) > 5,
                "content_density": 0,
                "professional_formatting": False
            },
            "processing_recommendations": []
        }

        content = extracted_data.get("content", "")
        if content:
            # Analyze content density
            structure["credibility_indicators"]["content_density"] = len(content.split()) / max(len(content), 1)
            
            # Check for section headers (common in financial documents)
            common_headers = [
                "BUSINESS", "RISK FACTORS", "MANAGEMENT", "FINANCIAL", 
                "OPERATIONS", "LIQUIDITY", "CONTROLS", "LEGAL"
            ]
            
            for header in common_headers:
                if header in content.upper():
                    structure["section_headers"].append(header)
            
            structure["has_formal_structure"] = len(structure["section_headers"]) > 2
            structure["credibility_indicators"]["professional_formatting"] = structure["has_formal_structure"]
        
        # Processing recommendations based on structure
        if structure["has_formal_structure"]:
            structure["processing_recommendations"].append("Use section-aware chunking")
        
        if structure["credibility_indicators"]["has_tables"]:
            structure["processing_recommendations"].append("Extract and preserve table structure")
        
        if structure["credibility_indicators"]["content_density"] > 0.1:
            structure["processing_recommendations"].append("Use semantic chunking with overlap")
        
        return structure
    
    except Exception as e:
        logger.error(f"Error analyzing document structure: {str(e)}")
        return {"error": str(e)}
    