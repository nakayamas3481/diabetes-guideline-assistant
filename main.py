from typing import List
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from qdrant_client import QdrantClient

from config import settings
from services.pdf_service import extract_pages
from services.embeddings_service import detect_embedding_dim
from services.qdrant_service import create_qdrant_client, ensure_collection


DOC_PAGES: List[dict] = []
QDRANT_CLIENT: QdrantClient | None = None
QDRANT_MODE: str | None = None
OPENAI_CLIENT: OpenAI | None = None
EMBED_DIM: int | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global QDRANT_CLIENT, QDRANT_MODE, OPENAI_CLIENT, EMBED_DIM

    # --- startup（起動時に1回）---
    mode = settings.qdrant_mode()
    QDRANT_CLIENT, QDRANT_MODE = create_qdrant_client(
        mode=mode,
        url=str(settings.QDRANT_URL) if settings.QDRANT_URL else None,
        api_key=settings.QDRANT_API_KEY.get_secret_value() if settings.QDRANT_API_KEY else None,
        path=settings.QDRANT_PATH,
    )

    QDRANT_CLIENT.get_collections()

    OPENAI_CLIENT = OpenAI(api_key=settings.OPENAI_API_KEY.get_secret_value())

    EMBED_DIM = detect_embedding_dim(OPENAI_CLIENT, settings.OPENAI_EMBEDDING_MODEL)
    ensure_collection(QDRANT_CLIENT, settings.QDRANT_COLLECTION, EMBED_DIM)

    yield

    # --- shutdown（終了時に1回）---
    QDRANT_CLIENT = None
    OPENAI_CLIENT = None
    EMBED_DIM = None
    QDRANT_MODE = None


app = FastAPI(title="Diabetes Guideline Assistant", lifespan=lifespan)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "qdrant_mode": settings.qdrant_mode(),
        "collection": settings.QDRANT_COLLECTION,
        "embedding_model": settings.OPENAI_EMBEDDING_MODEL,
    }

class IngestRequest(BaseModel):
    pdf_path: str

@app.post("/ingest")
def ingest(req: IngestRequest):
    global DOC_PAGES
    DOC_PAGES = extract_pages(req.pdf_path)
    return {"ok": True, "pages": len(DOC_PAGES)}

@app.get("/debug/pdf")
def debug_pdf(page: int = 1, chars: int = 300):
    if not DOC_PAGES:
        raise HTTPException(status_code=400, detail="No document ingested yet. Call POST /ingest first.")
    if page < 1 or page > len(DOC_PAGES):
        raise HTTPException(status_code=400, detail=f"page must be between 1 and {len(DOC_PAGES)}")

    text = DOC_PAGES[page - 1]["text"] or ""
    return {"pages": len(DOC_PAGES), "page": page, "preview": text[:chars]}

@app.get("/debug/qdrant")
def debug_qdrant():
    if QDRANT_CLIENT is None:
        raise HTTPException(status_code=500, detail="Qdrant client not initialized")

    cols = QDRANT_CLIENT.get_collections()
    names = [c.name for c in cols.collections]

    return {
        "mode": QDRANT_MODE,
        "collection": settings.QDRANT_COLLECTION,
        "embedding_model": settings.OPENAI_EMBEDDING_MODEL,
        "embedding_dim": EMBED_DIM,
        "collections": names,
    }