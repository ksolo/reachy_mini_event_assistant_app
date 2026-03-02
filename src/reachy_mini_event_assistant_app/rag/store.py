import logging
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams


logger = logging.getLogger(__name__)

COLLECTION_NAME = "event_content"
VECTOR_SIZE = 1536  # text-embedding-3-small


class VectorStore:
    def __init__(self, path: str) -> None:
        Path(path).mkdir(parents=True, exist_ok=True)
        self._client = QdrantClient(path=path)
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        existing = {c.name for c in self._client.get_collections().collections}
        if COLLECTION_NAME not in existing:
            self._client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
            logger.info("Created Qdrant collection '%s'", COLLECTION_NAME)

    def is_empty(self) -> bool:
        info = self._client.get_collection(COLLECTION_NAME)
        return info.points_count == 0

    def upsert(self, points: list[PointStruct]) -> None:
        self._client.upsert(collection_name=COLLECTION_NAME, points=points)

    def delete_by_file(self, file_path: str) -> None:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        self._client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[FieldCondition(key="source_file", match=MatchValue(value=file_path))]
            ),
        )

    def search(self, query_vector: list[float], category: str | None = None, limit: int = 5) -> list[dict]:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        query_filter = None
        if category:
            query_filter = Filter(
                must=[FieldCondition(key="category", match=MatchValue(value=category))]
            )

        results = self._client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
        return [{"text": r.payload["text"], "source": r.payload["source_file"], "score": r.score} for r in results]
