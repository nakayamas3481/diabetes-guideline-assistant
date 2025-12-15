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