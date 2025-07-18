import os
import logging
from typing import Dict

try:
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.ai.documentintelligence.models import DocumentAnalysisFeature
except ImportError:
    # Fallback for missing document intelligence module
    DocumentIntelligenceClient = None
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.core.credentials import AzureKeyCredential

from ..core.config import settings


logger = logging.getLogger(__name__)


class MockSearchClient:
    def __init__(self):
        self.documents = []
    
    def upload_documents(self, documents):
        self.documents.extend(documents)
        return {"status": "success", "count": len(documents)}
    
    def search(self, search_text=None, vector_queries=None, **kwargs):
        return [
            {
                "id": "mock-doc-1",
                "content": "Sample financial content from 10-K report",
                "title": "Sample Financial Corporation 10-K",
                "document_type": "10-K",
                "company": "Sample Financial Corporation",
                "filing_date": "2023-12-31",
                "source": "mock://sample-10k.pdf",
                "credibility_score": 0.95
            }
        ]


class MockSearchIndexClient:
    def create_or_update_index(self, index):
        return {"status": "success", "name": index.name}
    
    def delete_index(self, index_name):
        return {"status": "success", "deleted": index_name}
    
    def get_index(self, index_name):
        from azure.search.documents.indexes.models import SearchIndex, SimpleField, SearchFieldDataType
        return SearchIndex(
            name=index_name,
            fields=[SimpleField(name="id", type=SearchFieldDataType.String, key=True)]
        )

class MockDocumentIntelligenceClient:
    def begin_analyze_document(self, model_id, body, content_type="application/pdf"):
        class MockPoller:
            def result(self):
                class MockResult:
                    def __init__(self):
                        self.content = "Mock extracted content from financial document"
                        self.pages = [{"page_number": 1}]
                        self.tables = []
                        self.key_value_pairs = []
                return MockResult()
        return MockPoller()


class MockOpenAIClient:
    def __init__(self):
        self.embeddings = MockEmbeddings()


class MockEmbeddings:
    def create(self, input, model):
        class MockResponse:
            def __init__(self):
                self.data = [MockEmbeddingData()]
        return MockResponse()


class MockEmbeddingData:
    def __init__(self):
        import random

        self.embedding = [random.random() for _ in range(1536)]

class AzureServiceManager:
    def __init__(self):
        self.search_client = None
        self.form_recognizer_client = None
        self.credential = None
        self._use_mock = os.getenv("MOCK_AZURE_SERVICES", "false").lower() == "true"
    
    async def initialize(self):
        """Initialize all Azure services."""
        try:
            if self._use_mock:
                logger.info("Initializing mock Azure services for development.")
                await self._initialize_mock_services()
                return

            logger.info("Initializing real Azure services...")

            # Initialize credentials
            if settings.search_admin_key:
                # UUse API key authentication if available
                self.search_credential = AzureKeyCredential(settings.search_admin_key)
                logger.info("Using API key authentication for Azure Search")
            elif settings.azure_client_secret and settings.azure_tenant_id and settings.azure_client_id:
                # Use Service Principal authentication
                self.credential = ClientSecretCredential(
                    tenant_id=settings.azure_tenant_id,
                    client_id=settings.azure_client_id,
                    client_secret=settings.azure_client_secret
                )
                self.search_credential = self.credential
                logger.info("Using Service Principal authentication")
            else:
                # Use default Azure credential
                self.credential = DefaultAzureCredential()
                self.search_credential = self.credential
                logger.info("Using Default Azure Credential")

            # Initialize Document Inteeligence client
            if hasattr(settings, "document_intel_account_url") and settings.document_intel_account_url:
                if isinstance(self.search_credential, AzureKeyCredential):
                    # For API key auth, we need a separate DI key
                    di_credential = AzureKeyCredential(getattr(settings, 'document_intel_key', ''))
                else:
                    di_credential = self.search_credential
                
                self.form_recognizer_client = DocumentIntelligenceClient(
                    endpoint=settings.document_intel_account_url,
                    credential=di_credential
                )
                logger.info("Document Intelligence client initialized")
            else:
                logger.warning("Document Intelligence endpoint not configured")
                self.form_recognizer_client = None

        except Exception as e:
            logger.error(f"Failed to initialize Azure services: {e}")
    
    def _select_document_model(self, content_type: str, filename: str = None) -> str:
        """Select appropriate Document Intelligence model based on content type and filename."""
        if filename:
            filename_lower = filename.lower()
            if any(term in filename_lower for term in ['10-k', '10k', '10-q', '10q', 'annual', 'quarterly']):
                return "prebuilt-layout"  # Best for structured financial documents
        
        if content_type == "application/pdf":
            return "prebuilt-layout"
        elif content_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"]:
            return "prebuilt-document"
        else:
            return "prebuilt-document"

    async def _initialize_mock_services(self):
        """Initialize mock services for local development"""
        self.search_client = MockSearchClient()
        self.async_search_client = MockSearchClient()
        self.search_index_client = MockSearchIndexClient()
        self.form_recognizer_client = MockDocumentIntelligenceClient()
        self.openai_client = MockOpenAIClient()
        self.async_openai_client = MockOpenAIClient()
        self.cosmos_client = None  # Mock CosmosDB not needed for basic functionality
        self.credential = None
        self._use_mock = True
        
        logger.info("Mock Azure services initialized for local development")

    async def analyze_document(self, document_content: bytes, content_type: str, filename: str = None) -> Dict:
        """Analyze document using Azure Document Intelligence"""
        try:
            if not self.form_recognizer_client:
                raise ValueError("Document Intelligence client is not initialized")
            
            model_id = self._select_document_model(content_type, filename)
            logger.info(f"Analyzing document with model {model_id}, size: {len(document_content)} bytes")
            
            poller = self.form_recognizer_client.begin_analyze_document(
                model_id=model_id,
                body=document_content,
                content_type=content_type,
                # features=[DocumentAnalysisFeature.KEY_VALUE_PAIRS]  # 키-값 추출 활성화  
            )

            result = poller.result()

            extracted_content = {
                "content": result.content,
                "tables": [],
                "key_value_pairs": {},
                "pages": len(result.pages) if result.pages else 0,
                "metadata": {
                    "model_used": model_id,
                    "confidence_scores": {}
                }
            }

            # Extract tables
            if result.tables:
                for i, table in enumerate(result.tables):
                    table_data = {
                        "table_id": i,
                        "cells": []
                    }
                    
                    for cell in table.cells:
                        table_data["cells"].append({
                            "content": cell.content,
                            "row_index": cell.row_index,
                            "column_index": cell.column_index,
                            "confidence": getattr(cell, 'confidence', 0.0)
                        })
                    
                    extracted_content["tables"].append(table_data)

            # Extract key-value pairs
            if result.key_value_pairs:
                for kv_pair in result.key_value_pairs:
                    if kv_pair.key and kv_pair.value:
                        key_content = kv_pair.key.content
                        value_content = kv_pair.value.content
                        
                        extracted_content["key_value_pairs"][key_content] = {
                            "value": value_content,
                            "confidence": getattr(kv_pair, 'confidence', 0.0)
                        }
            
            logger.info(f"Document analysis completed: {extracted_content['pages']} pages, {len(extracted_content['tables'])} tables")
            return extracted_content  # , result

        except Exception as e:
            logger.error(f"Document analysis failed: {e}")
            raise


# Global service manager instance
azure_service_manager = AzureServiceManager()

async def get_azure_service_manager() -> AzureServiceManager:
    """Get the global Azure service manager instance"""
    if not azure_service_manager.search_client:
        await azure_service_manager.initialize()
    return azure_service_manager