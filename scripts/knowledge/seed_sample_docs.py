import asyncio
from pathlib import Path

from app.admin_store import AdminStore
from app.documents import iter_supported_files, read_text_file
from app.training import run_training_job
from app.whatsapp import COURSE_ORDER


def infer_courses(path: Path) -> list[str]:
    lower = path.name.casefold()
    matched = [course for course in COURSE_ORDER if course.casefold() in lower]
    return matched or list(COURSE_ORDER)


async def main() -> None:
    data_dir = Path("/app/data/sample_docs")
    if not data_dir.exists():
        data_dir = Path(__file__).resolve().parents[2] / "data" / "sample_docs"
    store = AdminStore()
    document_ids: list[str] = []

    for path in iter_supported_files(data_dir):
        content = (await asyncio.to_thread(read_text_file, path)).strip()
        source_name = str(path.relative_to(data_dir.parent)).replace("\\", "/")
        doc_type = "job_hunt" if "job" in path.name.casefold() else "lesson"
        for course in infer_courses(path):
            existing = await store.find_document(source_name, course)
            if existing:
                document = await store.update_document(
                    existing["id"],
                    title=path.stem,
                    course=course,
                    doc_type=doc_type,
                    content=content,
                    expected_version=int(existing["version"]),
                )
            else:
                document = await store.create_document(
                    title=path.stem,
                    filename=source_name,
                    course=course,
                    doc_type=doc_type,
                    content=content,
                )
            document_ids.append(document["id"])

    if not document_ids:
        raise SystemExit("No supported sample documents were found")
    job = await store.create_training_job(document_ids)
    await run_training_job(job["id"])
    completed = await store.get_training_job(job["id"])
    if completed is None:
        raise SystemExit("Training job record was lost")
    print(
        f"Sample knowledge job {completed['status']}: "
        f"files={completed['total_documents']}, chunks={completed['total_chunks']}"
    )


if __name__ == "__main__":
    asyncio.run(main())
