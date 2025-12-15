from openai import OpenAI

def embed_text(client: OpenAI, model: str, text: str) -> list[float]:
    if not text.strip():
        raise ValueError("Embedding input must be non-empty")

    resp = client.embeddings.create(
        model=model,
        input=text,
    )
    return resp.data[0].embedding

def detect_embedding_dim(client: OpenAI, model: str) -> int:
    vec = embed_text(client, model, "dimension probe")
    return len(vec)

def embed_texts(client: OpenAI, model: str, texts: list[str]) -> list[list[float]]:
    cleaned = [t.strip() for t in texts if t and t.strip()]
    if not cleaned:
        return []

    resp = client.embeddings.create(
        model=model,
        input=cleaned,
    )
    return [d.embedding for d in resp.data]