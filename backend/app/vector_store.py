from uuid import uuid4
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from .config import get_settings
from .schemas import SourceChunk


class VectorStore:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = AsyncQdrantClient(
            url=self.settings.qdrant_url,
            api_key=self.settings.qdrant_api_key or None,
            timeout=self.settings.request_timeout_seconds,
        )

    async def ensure_collection(self) -> None:
        collections = await self.client.get_collections()
        names = {c.name for c in collections.collections}
        if self.settings.qdrant_collection in names:
            return

        await self.client.create_collection(
            collection_name=self.settings.qdrant_collection,
            vectors_config=models.VectorParams(
                size=self.settings.embedding_dimensions,
                distance=models.Distance.COSINE,
            ),
            hnsw_config=models.HnswConfigDiff(
                m=32,
                ef_construct=128,
                full_scan_threshold=10000,
            ),
            optimizers_config=models.OptimizersConfigDiff(
                indexing_threshold=20000,
            ),
        )

        # Payload indexes make metadata filters fast when the KB grows.
        for field in ("course", "doc_type", "source_id"):
            try:
                await self.client.create_payload_index(
                    collection_name=self.settings.qdrant_collection,
                    field_name=field,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
            except Exception:
                pass

    async def upsert_chunks(
        self,
        *,
        texts: list[str],
        embeddings: list[list[float]],
        title: str,
        source_id: str,
        course: str,
        doc_type: str,
        url: str | None = None,
    ) -> int:
        await self.ensure_collection()

        points = []
        for idx, (text, vector) in enumerate(zip(texts, embeddings)):
            points.append(
                models.PointStruct(
                    id=str(uuid4()),
                    vector=vector,
                    payload={
                        "source_id": source_id,
                        "title": title,
                        "course": course.upper(),
                        "doc_type": doc_type,
                        "chunk_index": idx,
                        "text": text,
                        "url": url,
                    },
                )
            )

        if points:
            await self.client.upsert(
                collection_name=self.settings.qdrant_collection,
                points=points,
                wait=False,
            )

        return len(points)

    async def search(
        self,
        *,
        query_vector: list[float],
        course: str,
        top_k: int | None = None,
    ) -> list[SourceChunk]:
        await self.ensure_collection()

        should_filters = [
            models.FieldCondition(
                key="course",
                match=models.MatchValue(value=course.upper()),
            ),
            models.FieldCondition(
                key="course",
                match=models.MatchValue(value="GENERAL"),
            ),
        ]

        result = await self.client.search(
            collection_name=self.settings.qdrant_collection,
            query_vector=query_vector,
            limit=top_k or self.settings.top_k,
            query_filter=models.Filter(should=should_filters),
            with_payload=True,
        )

        chunks: list[SourceChunk] = []
        for point in result:
            payload = point.payload or {}
            chunks.append(
                SourceChunk(
                    source_id=str(payload.get("source_id", "")),
                    title=str(payload.get("title", "")),
                    course=str(payload.get("course", "")),
                    doc_type=str(payload.get("doc_type", "")),
                    text=str(payload.get("text", "")),
                    score=float(point.score) if point.score is not None else None,
                )
            )

        return chunks
