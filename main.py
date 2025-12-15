from typing import List
from contextlib import asynccontextmanager
from pathlib import Path
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from openai import OpenAI
from qdrant_client import QdrantClient
import uuid

from config import settings
from services.pdf_service import extract_pages, pages_to_chunks
from services.embeddings_service import detect_embedding_dim, embed_texts, embed_text
from services.qdrant_service import create_qdrant_client, ensure_collection, upsert_chunks, search_similar


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
    if QDRANT_CLIENT is None or OPENAI_CLIENT is None or EMBED_DIM is None:
        raise HTTPException(status_code=500, detail="Services not initialized")

    # 1) PDF → pages
    DOC_PAGES = extract_pages(req.pdf_path)

    # 2) pages → chunks
    chunks = pages_to_chunks(DOC_PAGES, chunk_size=1000, overlap=150)
    texts = [c["text"] for c in chunks]

    # 3) embeddings（まとめて）
    vectors = embed_texts(OPENAI_CLIENT, settings.OPENAI_EMBEDDING_MODEL, texts)
    if len(vectors) != len(texts):
        raise HTTPException(status_code=500, detail="Embedding count mismatch")

    # 4) Qdrant upsert
    src = Path(req.pdf_path).name
    ids = [
        str(uuid.uuid5(uuid.NAMESPACE_URL, f"{src}|p{c['page']}|c{c['chunk_index']}"))
        for c in chunks
    ]
    payloads = [
        {"source": src, "page": c["page"], "chunk_index": c["chunk_index"], "text": c["text"]}
        for c in chunks
    ]
    upsert_chunks(QDRANT_CLIENT, settings.QDRANT_COLLECTION, ids, vectors, payloads)

    return {"ok": True, "pages": len(DOC_PAGES), "chunks": len(chunks)}

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

@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    if QDRANT_CLIENT is None or OPENAI_CLIENT is None:
        raise HTTPException(status_code=500, detail="Services not initialized")

    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question must be non-empty")

    # 1) 質問をembedding
    qvec = embed_text(OPENAI_CLIENT, settings.OPENAI_EMBEDDING_MODEL, req.question)

    # 2) Qdrant検索
    hits = search_similar(
        QDRANT_CLIENT,
        settings.QDRANT_COLLECTION,
        qvec,
        top_k=req.top_k,
    )

    # 3) evidence形式に整形（payloadから取り出す）
    evidence = []
    for h in hits:  # h は dict
        evidence.append(
            Evidence(
                page=int(h.get("page") or 0),
                text=(h.get("text") or "")[:500],
                score=float(h.get("score") or 0.0),
            )
        )

    # 4) まずはテンプレ回答（次ステップで拡張）
    answer = "関連箇所（根拠）を表示します。" if evidence else "文書内に明確な記載が見つかりませんでした。"
    category = "Unknown" 

    return {"answer": answer, "category": category, "evidence": evidence}

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