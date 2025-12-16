# Diabetes Guideline Assistant

Clinical guideline QA (RAG) app with FastAPI + Qdrant + OpenAI and React Router frontend.

## Prerequisites
- Python 3.11+ (venv recommended)
- Node.js 18+ (frontend build/dev tooling)
- OpenAI API key
- Qdrant: cloud URL+API key **or** local `.qdrant` directory (default)

## Setup (local)
1) Clone repo
```
git clone <REPO_URL>
cd diabetes-guideline-assistant
```

2) Python deps
```
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
```

3) Env vars (`.env` at repo root)
```
OPENAI_API_KEY=sk-...
OPENAI_CHAT_MODEL=gpt-5.2
OPENAI_EMBEDDING_MODEL=text-embedding-3-large

# Qdrant: choose one mode
# Cloud
# QDRANT_URL=https://xxxx.qdrant.cloud
# QDRANT_API_KEY=...

# Local (default)
QDRANT_PATH=.qdrant
QDRANT_COLLECTION=who_diabetes_guideline
```
Only one of `QDRANT_URL` or `QDRANT_PATH` should be set.

4) Ingest source PDF
Place your PDF (e.g., `content.pdf`) in repo root or provide a full path.

5) Run backend
```
.venv/Scripts/activate
fastapi dev main.py
```

6) Run frontend
```
cd frontend
npm install
npm run dev -- --host --port 5173
```
Open http://localhost:5173

## Usage flow
1) Ingest: UI “Ingest” screen → pdf_path = `content.pdf` → ingest.
2) Query: UI “Query” screen → ask question. Evidence and categories return; feedback (👍/👎 + optional comment) is stored locally.
3) History: UI “History” screen → search, re-run, delete, view feedback/evidence.
