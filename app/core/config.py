from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    search_admin_key: str = os.getenv("SEARCH_ADMIN_KEY", "")

    azure_client_secret: Optional[str] = os.getenv("AZURE_CLIENT_SECRET", "")
    azure_tenant_id: Optional[str] = os.getenv("AZURE_TENANT_ID", "")
    azure_client_id: Optional[str] = os.getenv("AZURE_CLIENT_ID", "")

    document_intel_account_url: str = ""
    document_intel_key: str = ""

    chunk_size: int = int(os.getenv("CHUNK_SIZE", "1000"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "200"))

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
