from fastapi import FastAPI

app = FastAPI(title="Diabetes Guideline Assistant")

@app.get("/health")
def health():
    return {"status": "ok"}
