from typing import List
from pypdf import PdfReader

def extract_pages(pdf_path: str) -> List[dict]:
    reader = PdfReader(pdf_path)
    pages: List[dict] = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append({"page": i, "text": text})
    return pages

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> List[str]:
    text = text or ""
    if not text.strip():
        return []

    chunks: List[str] = []
    step = max(1, chunk_size - overlap)
    for start in range(0, len(text), step):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
    return chunks

def pages_to_chunks(pages: List[dict], chunk_size: int = 1000, overlap: int = 150) -> List[dict]:
    """
    pages: [{"page": 1, "text": "..."}]
    return: [{"page": 1, "chunk_index": 0, "text": "..."}, ...]
    """
    out: List[dict] = []
    for p in pages:
        page_no = p["page"]
        for idx, ch in enumerate(chunk_text(p.get("text", ""), chunk_size, overlap)):
            out.append({"page": page_no, "chunk_index": idx, "text": ch})
    return out