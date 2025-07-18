from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .api.doc_parsing import router as doc_parsing_router


VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager to initialize resources.
    """
    yield


app = FastAPI(title="Document Parsing MCP Server",
              version=VERSION,
              lifespan=lifespan
              )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(doc_parsing_router, prefix="/api/documents")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"message": "Document Parsing MCP Server using Azure Document Intelligence", "version": VERSION}