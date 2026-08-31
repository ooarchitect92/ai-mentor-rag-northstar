import asyncio
import sys
from pathlib import Path

from app.admin_store import AdminStore
from app.documents import iter_supported_files, read_text_file
from app.training import run_training_job
from app.whatsapp import COURSE_ORDER


def infer_course(path: Path) -> str | None:
    haystack = str(path).casefold()
    return next((course for course in COURSE_ORDER if course.casefold() in haystack), None)


async def main() -> None:
    if len(sys.argv) not in {2, 3}:
        raise SystemExit(
            "Usage: python scripts/knowledge/ingest_directory.py /path/to/docs [CMA|CPA|CFA|ACCA|CS|EA]"
        )

    directory = Path(sys.argv[1]).resolve()
    if not directory.is_dir():
        raise SystemExit(f"Directory not found: {directory}")
    explicit_course = sys.argv[2].upper() if len(sys.argv) == 3 else None
    if explicit_course and explicit_course not in COURSE_ORDER:
        raise SystemExit("Course must be CMA, CPA, CFA, ACCA, CS, or EA")

    store = AdminStore()
    document_ids: list[str] = []
    for path in iter_supported_files(directory):
        course = explicit_course or infer_course(path)
        if course is None:
            print(f"Skipping {path}: course is not present in the path; pass a course argument")
            continue
        print(f"Preparing {path} for {course}")
        content = (await asyncio.to_thread(read_text_file, path)).strip()
        source_name = str(path.relative_to(directory)).replace("\\", "/")
        existing = await store.find_document(source_name, course)
        if existing:
            document = await store.update_document(
                existing["id"],
                title=path.stem,
                course=course,
                doc_type="other",
                content=content,
                expected_version=int(existing["version"]),
            )
        else:
            document = await store.create_document(
                title=path.stem,
                filename=source_name,
                course=course,
                doc_type="other",
                content=content,
            )
        document_ids.append(document["id"])

    if not document_ids:
        raise SystemExit("No documents were prepared; check file types and course mapping")
    job = await store.create_training_job(document_ids)
    await run_training_job(job["id"])
    completed = await store.get_training_job(job["id"])
    if completed is None:
        raise SystemExit("Training job record was lost")
    print(
        f"Knowledge job {completed['status']}: "
        f"files={completed['total_documents']}, chunks={completed['total_chunks']}"
    )


if __name__ == "__main__":
    asyncio.run(main())
