from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

logger = logging.getLogger("rag.qdrant")


class VectorStoreUnavailable(Exception):
    pass


class QdrantStore:
    def __init__(self, url: str, collection: str, client: QdrantClient | None = None):
        self.collection = collection
        self.client = client or QdrantClient(url=url)
        self._collection_ready = False

    def ensure_collection(self, vector_size: int) -> None:
        if self._collection_ready:
            return
        try:
            info = self.client.get_collection(self.collection)
            existing_size = info.config.params.vectors.size
            if existing_size != vector_size:
                logger.warning(
                    "Qdrant collection vector size mismatch: existing=%s expected=%s",
                    existing_size,
                    vector_size,
                )
            self._collection_ready = True
            return
        except Exception:
            logger.info("Qdrant collection missing; creating '%s'", self.collection)

        try:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            self._collection_ready = True
        except Exception as exc:
            logger.warning("Qdrant create collection failed: %s", exc)
            raise VectorStoreUnavailable("Vector store unavailable") from exc

    def upsert_chunks(self, points: list[PointStruct]) -> None:
        if not points:
            return
        try:
            self.client.upsert(collection_name=self.collection, points=points)
        except Exception as exc:
            logger.warning("Qdrant upsert failed: %s", exc)
            raise VectorStoreUnavailable("Vector store unavailable") from exc

    def search(self, query_vector: list[float], top_k: int) -> list[dict[str, Any]]:
        try:
            response = self.client.query_points(
                collection_name=self.collection,
                query=query_vector,
                limit=top_k,
                with_payload=True,
            )
        except Exception as exc:
            logger.warning("Qdrant search failed: %s", exc)
            raise VectorStoreUnavailable("Vector store unavailable") from exc

        output: list[dict[str, Any]] = []
        for result in response.points:
            payload = result.payload or {}
            output.append(
                {
                    "id": result.id,
                    "score": result.score,
                    "payload": payload,
                }
            )
        return output


def build_point(
    *,
    chunk_id: str,
    vector: list[float],
    doc_id: str,
    title: str,
    tags: list[str],
    lang: str,
    chunk_text: str,
    source_url: str | None = None,
) -> PointStruct:
    import uuid

    payload = {
        "doc_id": doc_id,
        "title": title,
        "chunk_id": chunk_id,
        "tags": tags,
        "lang": lang,
        "chunk_text": chunk_text,
        "source_url": source_url,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))
    return PointStruct(id=point_id, vector=vector, payload=payload)
