from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

def create_qdrant_client(mode: str, url: str | None, api_key: str | None, path: str | None) -> tuple[QdrantClient, str]:
    if mode == "cloud":
        client = QdrantClient(url=url, api_key=api_key)
        return client, "cloud"

    # local
    if path == ":memory:":
        client = QdrantClient(":memory:")
    else:
        client = QdrantClient(path=path)
    return client, "local"

def ensure_collection(client: QdrantClient, collection_name: str, vector_size: int) -> None:
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        return

    info = client.get_collection(collection_name)
    existing_size = info.config.params.vectors.size
    if existing_size != vector_size:
        raise RuntimeError(
            f"Collection '{collection_name}' already exists with size={existing_size}, "
            f"but embedding dim is {vector_size}. "
            f"Use a new collection name or delete/recreate the collection."
        )
    
def upsert_chunks(
    client: QdrantClient,
    collection_name: str,
    ids: list[str],
    vectors: list[list[float]],
    payloads: list[dict],
) -> None:
    points = [
        PointStruct(id=ids[i], vector=vectors[i], payload=payloads[i])
        for i in range(len(ids))
    ]
    client.upsert(collection_name=collection_name, points=points)