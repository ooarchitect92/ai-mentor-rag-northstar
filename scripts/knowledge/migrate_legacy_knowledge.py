"""Adopt pre-dashboard Qdrant chunks into the editable knowledge catalog.

Run without --apply for a read-only inventory. With --apply, legacy chunks are
reconstructed into source documents and re-indexed with revision/fingerprint
metadata. Old points remain stored but are excluded by retrieval filters.
"""

import argparse
import asyncio
import hashlib
from collections import defaultdict
from pathlib import PurePosixPath
from typing import Any

from app.admin_store import AdminStore, VersionConflictError
from app.training import run_training_job
from app.vector_store import VectorStore
from app.whatsapp import COURSE_ORDER


DOCUMENT_TYPES = {"lesson", "notes", "faq", "quiz", "job_hunt", "policy", "other"}


def source_filename(source_id: str) -> str:
    basename = PurePosixPath(source_id.replace("\\", "/")).name or "legacy-source.txt"
    digest = hashlib.sha256(source_id.encode("utf-8")).hexdigest()[:10]
    return f"legacy/{digest}-{basename}"[:500]


async def read_legacy_sources(vector_store: VectorStore) -> list[dict[str, Any]]:
    await vector_store.ensure_collection()
    grouped: dict[tuple[str, str, str, str], list[tuple[int, str]]] = defaultdict(list)
    offset = None
    while True:
        points, offset = await vector_store.client.scroll(
            collection_name=vector_store.settings.qdrant_collection,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in points:
            payload = point.payload or {}
            if payload.get("source_revision"):
                continue
            source_id = str(payload.get("source_id") or "").strip()
            course = str(payload.get("course") or "").strip().upper()
            text = str(payload.get("text") or "").strip()
            if not source_id or course not in COURSE_ORDER or not text:
                continue
            doc_type = str(payload.get("doc_type") or "other").strip().lower()
            if doc_type not in DOCUMENT_TYPES:
                doc_type = "other"
            title = str(payload.get("title") or source_id).strip()[:300]
            try:
                chunk_index = int(payload.get("chunk_index") or 0)
            except (TypeError, ValueError):
                chunk_index = 0
            grouped[(source_id, course, doc_type, title)].append((chunk_index, text))
        if offset is None:
            break

    sources = []
    for (source_id, course, doc_type, title), chunks in grouped.items():
        sources.append(
            {
                "source_id": source_id,
                "filename": source_filename(source_id),
                "course": course,
                "doc_type": doc_type,
                "title": title,
                "content": "\n\n".join(text for _, text in sorted(chunks)),
                "chunks": len(chunks),
            }
        )
    return sources


async def apply_migration(sources: list[dict[str, Any]]) -> None:
    store = AdminStore()
    document_ids: list[str] = []
    for source in sources:
        existing = await store.find_document(source["filename"], source["course"])
        if existing is not None and existing["status"] in {"queued", "indexing", "deleting"}:
            print(f"Skipping busy source {source['source_id']}: status={existing['status']}")
            continue
        try:
            if existing is None:
                document = await store.create_document(
                    title=source["title"],
                    filename=source["filename"],
                    course=source["course"],
                    doc_type=source["doc_type"],
                    content=source["content"],
                )
            elif existing["content"] != source["content"]:
                document = await store.update_document(
                    existing["id"],
                    title=source["title"],
                    course=source["course"],
                    doc_type=source["doc_type"],
                    content=source["content"],
                    expected_version=int(existing["version"]),
                )
            else:
                document = existing
        except VersionConflictError as exc:
            print(f"Skipping busy source {source['source_id']}: {exc}")
            continue
        document_ids.append(str(document["id"]))

    for start in range(0, len(document_ids), 25):
        batch = document_ids[start : start + 25]
        job = await store.create_training_job(batch)
        await run_training_job(str(job["id"]))
        completed = await store.get_training_job(job["id"])
        if completed is None:
            raise RuntimeError("Migration training job record was lost")
        print(
            f"Migration job {completed['id'][:8]}: {completed['status']}, "
            f"documents={completed['total_documents']}, chunks={completed['total_chunks']}"
        )


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write adopted sources to SQLite and publish new Qdrant revisions",
    )
    args = parser.parse_args()

    sources = await read_legacy_sources(VectorStore())
    print(
        f"Found {len(sources)} legacy source(s) containing "
        f"{sum(source['chunks'] for source in sources)} chunk(s)."
    )
    if not args.apply:
        print("Read-only inventory complete. Run again with --apply to adopt and re-index them.")
        return
    if not sources:
        print("Nothing to migrate.")
        return
    await apply_migration(sources)


if __name__ == "__main__":
    asyncio.run(main())
