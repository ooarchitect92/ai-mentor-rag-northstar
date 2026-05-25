import asyncio
import sys
from pathlib import Path
from app.chunking import chunk_text
from app.documents import read_text_file, iter_supported_files
from app.embeddings import EmbeddingService
from app.vector_store import VectorStore


def infer_course(path: Path) -> str:
    haystack = str(path).lower()
    for course in ("cma", "cpa", "acca", "ea"):
        if course in haystack:
            return course.upper()
    return "GENERAL"


async def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python scripts/ingest_directory.py /path/to/docs")

    directory = Path(sys.argv[1])
    if not directory.exists():
        raise SystemExit(f"Directory not found: {directory}")

    embedder = EmbeddingService()
    store = VectorStore()
    total_files = 0
    total_chunks = 0

    for path in iter_supported_files(directory):
        print(f"Ingesting {path}")
        text = read_text_file(path)
        chunks = chunk_text(text)
        texts = [chunk.text for chunk in chunks]
        vectors = await embedder.embed_many(texts)

        inserted = await store.upsert_chunks(
            texts=texts,
            embeddings=vectors,
            title=path.name,
            source_id=str(path),
            course=infer_course(path),
            doc_type="imported",
        )
        total_files += 1
        total_chunks += inserted

    print(f"Done. Files={total_files}, chunks={total_chunks}")


if __name__ == "__main__":
    asyncio.run(main())
