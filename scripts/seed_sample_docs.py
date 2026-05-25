import asyncio
from pathlib import Path
from app.chunking import chunk_text
from app.documents import read_text_file, iter_supported_files
from app.embeddings import EmbeddingService
from app.vector_store import VectorStore


async def main() -> None:
    data_dir = Path("/app/data/sample_docs")
    embedder = EmbeddingService()
    store = VectorStore()
    total = 0

    for path in iter_supported_files(data_dir):
        text = read_text_file(path)
        chunks = chunk_text(text)
        texts = [chunk.text for chunk in chunks]
        vectors = await embedder.embed_many(texts)

        course = "GENERAL"
        lower = path.name.lower()
        if "cma" in lower:
            course = "CMA"
        elif "cpa" in lower:
            course = "CPA"
        elif "acca" in lower:
            course = "ACCA"
        elif "ea" in lower:
            course = "EA"

        total += await store.upsert_chunks(
            texts=texts,
            embeddings=vectors,
            title=path.name,
            source_id=str(path),
            course=course,
            doc_type="sample",
        )

    print(f"Seeded {total} chunks into Qdrant.")


if __name__ == "__main__":
    asyncio.run(main())
