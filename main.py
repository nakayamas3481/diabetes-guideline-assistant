from typing import List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
from openai import OpenAI
from contextlib import asynccontextmanager
from config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    global QDRANT_CLIENT, QDRANT_MODE, OPENAI_CLIENT, EMBED_DIM

    # --- startup（起動時に1回）---
    QDRANT_CLIENT, QDRANT_MODE = create_qdrant_client()
    QDRANT_CLIENT.get_collections()

    OPENAI_CLIENT = OpenAI(api_key=settings.OPENAI_API_KEY.get_secret_value())

    EMBED_DIM = detect_embedding_dim()
    ensure_collection(EMBED_DIM)

    yield  # ← ここから先が shutdown

    # --- shutdown（終了時に1回）---
    QDRANT_CLIENT = None
    OPENAI_CLIENT = None
    EMBED_DIM = None
    QDRANT_MODE = None

app = FastAPI(title="Diabetes Guideline Assistant", lifespan=lifespan)

DOC_PAGES: List[dict] = []
QDRANT_CLIENT: QdrantClient | None = None
QDRANT_MODE: str | None = None
OPENAI_CLIENT: OpenAI | None = None
EMBED_DIM: int | None = None

def create_qdrant_client() -> tuple[QdrantClient, str]:
    mode = settings.qdrant_mode()

    if mode == "cloud":
        client = QdrantClient(
            url=str(settings.QDRANT_URL),
            api_key=settings.QDRANT_API_KEY.get_secret_value() if settings.QDRANT_API_KEY else None,
        )
        return client, "cloud"

    # local mode
    if settings.QDRANT_PATH == ":memory:":
        client = QdrantClient(":memory:") 
    else:
        client = QdrantClient(path=settings.QDRANT_PATH) 
    return client, "local"

def ensure_collection(vector_size: int) -> None:
    assert QDRANT_CLIENT is not None

    name = settings.QDRANT_COLLECTION
    if not QDRANT_CLIENT.collection_exists(name):
        QDRANT_CLIENT.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        return

    # 既に存在する場合：サイズが合うかだけチェック（不一致は事故になるので止める）
    info = QDRANT_CLIENT.get_collection(name)
    existing_size = info.config.params.vectors.size
    if existing_size != vector_size:
        raise RuntimeError(
            f"Collection '{name}' already exists with size={existing_size}, "
            f"but embedding dim is {vector_size}. "
            f"Use a new collection name or delete/recreate the collection."
        )

def embed_text(text: str) -> list[float]:
    if OPENAI_CLIENT is None:
        raise RuntimeError("OpenAI client not initialized")
    if not text.strip():
        raise ValueError("Embedding input must be non-empty") 

    resp = OPENAI_CLIENT.embeddings.create(
        model=settings.OPENAI_EMBEDDING_MODEL,
        input=text,
    )
    return resp.data[0].embedding

def detect_embedding_dim() -> int:
    vec = embed_text("dimension probe")
    return len(vec)


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

class QueryRequest(BaseModel):
    question: str
    top_k: int = 5

class Evidence(BaseModel):
    page: int
    text: str
    score: float

class QueryResponse(BaseModel):
    answer: str
    category: str
    evidence: List[Evidence]

def extract_pages(pdf_path: str) -> List[dict]:
    reader = PdfReader(pdf_path)
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append({"page": i, "text": text})
    return pages

@app.post("/ingest")
def ingest(req: IngestRequest):
    global DOC_PAGES
    DOC_PAGES = extract_pages(req.pdf_path)
    return {"ok": True, "pages": len(DOC_PAGES)}

@app.get("/debug/pdf")
def debug_pdf(page: int = 1, chars: int = 300):
    text = DOC_PAGES[page - 1]["text"] or ""
    return {
        "pages": len(DOC_PAGES),
        "page": page,
        "preview": text[:chars],
    }

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