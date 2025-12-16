from typing import List
from contextlib import asynccontextmanager
from pathlib import Path
from pydantic import BaseModel
from fastapi import APIRouter, FastAPI, HTTPException
from openai import OpenAI
from qdrant_client import QdrantClient
import uuid
from datetime import datetime, timezone

from config import settings
from services.pdf_service import extract_pages, pages_to_chunks
from services.embeddings_service import detect_embedding_dim, embed_texts, embed_text
from services.qdrant_service import create_qdrant_client, delete_by_source, ensure_collection, upsert_chunks, search_similar
from services.answer_service import generate_answer


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
api = APIRouter(prefix="/api")

@api.get("/health")
def health():
    return {
        "status": "ok",
        "qdrant_mode": settings.qdrant_mode(),
        "collection": settings.QDRANT_COLLECTION,
        "embedding_model": settings.OPENAI_EMBEDDING_MODEL,
    }

class IngestRequest(BaseModel):
    pdf_path: str

@api.post("/ingest")
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

    # ★追加：この ingest 実行のタイムスタンプ（UTC）
    ingested_at = datetime.now(timezone.utc).isoformat()

    # 4) Qdrant upsert
    src = Path(req.pdf_path).name
    ids = [
        str(uuid.uuid5(uuid.NAMESPACE_URL, f"{src}|p{c['page']}|c{c['chunk_index']}"))
        for c in chunks
    ]
    payloads = [
        {
            "source": src,
            "page": c["page"],
            "chunk_index": c["chunk_index"],
            "text": c["text"],
            "ingested_at": ingested_at,
        }
        for c in chunks
    ]
    upsert_chunks(QDRANT_CLIENT, settings.QDRANT_COLLECTION, ids, vectors, payloads)

    return {"ok": True, "pages": len(DOC_PAGES), "chunks": len(chunks)}

@api.get("/qdrant/status")
def qdrant_status():
    if QDRANT_CLIENT is None:
        raise HTTPException(status_code=500, detail="Qdrant client not initialized")

    collection = settings.QDRANT_COLLECTION

    try:
        points_count = QDRANT_CLIENT.count(collection_name=collection, exact=True).count
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read qdrant status: {e}")

    sources: set[str] = set()
    last_ingested_at: str | None = None

    try:
        offset = None
        while True:
            points, offset = QDRANT_CLIENT.scroll(
                collection_name=collection,
                limit=256,
                with_payload=True,
                with_vectors=False,
                offset=offset,
            )

            for p in points:
                payload = p.payload or {}
                src = payload.get("source")
                if isinstance(src, str) and src:
                    sources.add(src)

                ts = payload.get("ingested_at")
                if isinstance(ts, str) and ts:
                    if last_ingested_at is None or ts > last_ingested_at:
                        last_ingested_at = ts

            if offset is None:
                break
    except Exception:
        sources = set()
        last_ingested_at = None

    return {
        "mode": QDRANT_MODE,
        "qdrant_path": str(settings.QDRANT_PATH) if settings.QDRANT_PATH else None,
        "collection": collection,
        "points_count": points_count,
        "embedding_model": settings.OPENAI_EMBEDDING_MODEL,
        "embedding_dim": EMBED_DIM,
        "sources": sorted(list(sources)),
        "last_ingested_at": last_ingested_at,
    }

class QueryRequest(BaseModel):
    question: str
    top_k: int = 5

class Evidence(BaseModel):
    source: str
    page: int
    text: str
    score: float

class QueryResponse(BaseModel):
    answer: str
    categories: List[str]
    evidence: List[Evidence]

from services.category_service import classify_categories

@api.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    if QDRANT_CLIENT is None or OPENAI_CLIENT is None:
        raise HTTPException(status_code=500, detail="Services not initialized")

    # 1) 質問をベクトル化
    qvec = embed_text(
        OPENAI_CLIENT,
        settings.OPENAI_EMBEDDING_MODEL,
        req.question,
    )

    # 2) Qdrantで検索してevidenceを作る
    hits = search_similar(
        QDRANT_CLIENT,
        settings.QDRANT_COLLECTION,
        query_vector=qvec,
        top_k=req.top_k,
    )

    evidence = [
        Evidence(source=h.get("source"), page=h.get("page") or 0, text=h.get("text") or "", score=h.get("score") or 0.0)
        for h in hits
    ]

    # 3) ここにカテゴリ推定を入れる
    categories = classify_categories(
        OPENAI_CLIENT,
        settings.OPENAI_CHAT_MODEL,
        req.question,
        [e.model_dump() for e in evidence],
    )

    # 4) カテゴリが0件なら早期リターン
    if not categories:
        return QueryResponse(
            answer="This question is outside the supported diabetes guideline topics, or no supporting evidence was retrieved.",
            categories=[],
            evidence=[],
        )

    # 5) 回答生成（既存の generate_answer を呼ぶ）
    answer = generate_answer(
        OPENAI_CLIENT,
        settings.OPENAI_CHAT_MODEL,
        req.question,
        [e.model_dump() for e in evidence],
    )

    return QueryResponse(answer=answer, categories=categories, evidence=evidence)


@api.get("/debug/pdf")
def debug_pdf(page: int = 1, chars: int = 300):
    if not DOC_PAGES:
        raise HTTPException(status_code=400, detail="No document ingested yet. Call POST /ingest first.")
    if page < 1 or page > len(DOC_PAGES):
        raise HTTPException(status_code=400, detail=f"page must be between 1 and {len(DOC_PAGES)}")

    text = DOC_PAGES[page - 1]["text"] or ""
    return {"pages": len(DOC_PAGES), "page": page, "preview": text[:chars]}

@api.get("/debug/qdrant")
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

app.include_router(api)