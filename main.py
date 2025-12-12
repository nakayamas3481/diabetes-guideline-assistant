from typing import List
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Diabetes Guideline Assistant")

@app.get("/health")
def health():
    return {"status": "ok"}

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

@app.post("/ingest")
def ingest(req: IngestRequest):
    return {"ok": True, "message": f"ingest placeholder: {req.pdf_path}"}

@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    return {
        "answer": "placeholder answer",
        "category": "Screening",
        "evidence": [
            {"page": 1, "text": "placeholder evidence text", "score": 0.0}
        ],
    }