"""Stores one vector per chunk in Chroma and finds the closest ones; the chunk text stays in SQLite."""

import logging
from dataclasses import dataclass

import chromadb
from chromadb.config import Settings as ChromaSettings

from eduagent.db.chunks import StoredChunk
from eduagent.db.files import Origin

log = logging.getLogger(__name__)

WHAT_IT_DOES = "Keeps the meaning-vector of every study chunk in Chroma and finds the chunks closest to a question."


@dataclass(frozen=True)
class DenseHit:
    chunk_id: str
    similarity: float  # 1 - cosine distance


class VectorStore:
    COLLECTION = "chunks"

    def __init__(self, port: int, host: str = "127.0.0.1"):
        self._client = chromadb.HttpClient(host=host, port=port, settings=ChromaSettings(anonymized_telemetry=False))
        # We always send our own vectors, so no embedding function (Chroma's default would download a model).
        self._collection = self._client.get_or_create_collection(
            self.COLLECTION, configuration={"hnsw": {"space": "cosine"}}, embedding_function=None
        )

    def upsert(self, chunks: list[StoredChunk], vectors: list[list[float]], uploaded_week: int) -> None:
        if not chunks:
            return
        self._collection.upsert(
            ids=[c.id for c in chunks],
            embeddings=vectors,
            metadatas=[
                {
                    "chunk_id": c.id,
                    "course_id": c.course_id,
                    "module_id": c.module_id or 0,
                    "origin": c.origin,
                    "file_id": c.file_id,
                    "kind": c.kind,
                    "uploaded_week": uploaded_week,
                }
                for c in chunks
            ],
        )

    def query(
        self,
        vector: list[float],
        course_id: int,
        origin: Origin,
        *,
        module_id: int | None = None,
        file_id: int | None = None,
        kind: str | None = None,
        chunk_ids: list[str] | None = None,
        k: int = 30,
    ) -> list[DenseHit]:
        if chunk_ids is not None and not chunk_ids:
            return []
        conditions: list[dict] = [{"course_id": course_id}, {"origin": origin}]
        if module_id is not None:
            conditions.append({"module_id": module_id})
        if file_id is not None:
            conditions.append({"file_id": file_id})
        if kind is not None:
            conditions.append({"kind": kind})
        if chunk_ids is not None:
            conditions.append({"chunk_id": {"$in": chunk_ids}})
        result = self._collection.query(
            query_embeddings=[vector], n_results=k, where={"$and": conditions}, include=["distances"]
        )
        return [DenseHit(cid, 1 - dist) for cid, dist in zip(result["ids"][0], result["distances"][0])]

    def delete_file(self, file_id: int) -> None:
        self._collection.delete(where={"file_id": file_id})

    def set_module(self, file_id: int, module_id: int | None) -> None:
        got = self._collection.get(where={"file_id": file_id}, include=["metadatas"])
        if not got["ids"]:
            return
        metas = [{**m, "module_id": module_id or 0} for m in got["metadatas"]]
        self._collection.update(ids=got["ids"], metadatas=metas)

    def count(self, file_id: int | None = None) -> int:
        if file_id is None:
            return self._collection.count()
        return len(self._collection.get(where={"file_id": file_id}, include=[])["ids"])
