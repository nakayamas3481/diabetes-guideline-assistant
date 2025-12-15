from typing import List
from pypdf import PdfReader

def extract_pages(pdf_path: str) -> List[dict]:
    reader = PdfReader(pdf_path)
    pages: List[dict] = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append({"page": i, "text": text})
    return pages