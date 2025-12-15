from typing import List
from fastapi import FastAPI
from pydantic import BaseModel
from pypdf import PdfReader
from config import settings

app = FastAPI(title="Diabetes Guideline Assistant")

DOC_PAGES: List[dict] = []

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