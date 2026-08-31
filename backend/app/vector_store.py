import hashlib
from uuid import NAMESPACE_URL, uuid5
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from .admin_store import AdminStore
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

    @property
    def embedding_fingerprint(self) -> str:
        model = (
            self.settings.openai_embedding_model
            if self.settings.embedding_provider == "openai"
            else "northstar-hash-v1"
        )
        value = (
            f"{self.settings.embedding_provider}:{model}:"
            f"{self.settings.embedding_dimensions}:chunks-v1"
        )
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]

    async def ensure_collection(self) -> None:
        collections = await self.client.get_collections()
        names = {c.name for c in collections.collections}
        if self.settings.qdrant_collection not in names:
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
        else:
            collection = await self.client.get_collection(self.settings.qdrant_collection)
            vector_config = collection.config.params.vectors
            configured_size = getattr(vector_config, "size", None)
            configured_distance = getattr(vector_config, "distance", None)
            if configured_size is not None and configured_size != self.settings.embedding_dimensions:
                raise RuntimeError(
                    "Qdrant collection vector size does not match EMBEDDING_DIMENSIONS; "
                    "create a new collection before changing embedding dimensions"
                )
            if configured_distance is not None and configured_distance != models.Distance.COSINE:
                raise RuntimeError("Qdrant collection distance must be cosine")

        # Payload indexes make metadata filters fast when the KB grows.
        for field in ("course", "doc_type", "source_id", "source_revision", "embedding_fingerprint"):
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
        revision: int = 1,
    ) -> int:
        if len(texts) != len(embeddings):
            raise ValueError("Each document chunk must have exactly one embedding")
        if any(len(vector) != self.settings.embedding_dimensions for vector in embeddings):
            raise ValueError("Embedding vector dimensions do not match the configured collection")
        await self.ensure_collection()

        points = []
        for idx, (text, vector) in enumerate(zip(texts, embeddings)):
            points.append(
                models.PointStruct(
                    id=str(uuid5(NAMESPACE_URL, f"{source_id}:{revision}:{idx}")),
                    vector=vector,
                    payload={
                        "source_id": source_id,
                        "title": title,
                        "course": course.upper(),
                        "doc_type": doc_type,
                        "chunk_index": idx,
                        "text": text,
                        "url": url,
                        "revision": revision,
                        "source_revision": f"{source_id}:{revision}",
                        "embedding_fingerprint": self.embedding_fingerprint,
                    },
                )
            )

        if points:
            await self.client.upsert(
                collection_name=self.settings.qdrant_collection,
                points=points,
                wait=True,
            )

        return len(points)

    async def delete_source(self, source_id: str) -> None:
        await self.ensure_collection()
        await self.client.delete(
            collection_name=self.settings.qdrant_collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source_id",
                            match=models.MatchValue(value=source_id),
                        )
                    ]
                )
            ),
            wait=True,
        )

    async def replace_source_chunks(
        self,
        *,
        texts: list[str],
        embeddings: list[list[float]],
        title: str,
        source_id: str,
        course: str,
        doc_type: str,
        revision: int,
    ) -> int:
        """Stage a deterministic revision; the metadata store activates it separately."""
        return await self.upsert_chunks(
            texts=texts,
            embeddings=embeddings,
            title=title,
            source_id=source_id,
            course=course,
            doc_type=doc_type,
            revision=revision,
        )

    async def prune_source_revisions(self, source_id: str, revision: int) -> None:
        """Remove superseded points after the metadata transaction has published a revision."""
        await self.ensure_collection()
        await self.client.delete(
            collection_name=self.settings.qdrant_collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source_id",
                            match=models.MatchValue(value=source_id),
                        )
                    ],
                    must_not=[
                        models.FieldCondition(
                            key="revision",
                            match=models.MatchValue(value=revision),
                        )
                    ],
                )
            ),
            wait=True,
        )

    async def search(
        self,
        *,
        query_vector: list[float],
        course: str,
        top_k: int | None = None,
    ) -> list[SourceChunk]:
        await self.ensure_collection()
        published_revisions = await AdminStore().list_published_source_revisions()
        if not published_revisions:
            return []

        course_filter = models.FieldCondition(
            key="course",
            match=models.MatchValue(value=course.upper()),
        )

        result = await self.client.search(
            collection_name=self.settings.qdrant_collection,
            query_vector=query_vector,
            limit=top_k or self.settings.top_k,
            query_filter=models.Filter(
                must=[
                    course_filter,
                    models.FieldCondition(
                        key="embedding_fingerprint",
                        match=models.MatchValue(value=self.embedding_fingerprint),
                    ),
                    models.FieldCondition(
                        key="source_revision",
                        match=models.MatchAny(any=published_revisions),
                    ),
                ]
            ),
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
