# Knowledge operations

Tools in this folder create or migrate editable knowledge and its derived RAG
index. Prefer the admin dashboard for everyday upload and training operations.

- `ingest_directory.py`: import a directory through the document catalog.
- `seed_sample_docs.py`: idempotently publish bundled examples.
- `migrate_legacy_knowledge.py`: inspect or adopt older Qdrant content.
- `verify_course_answers.py`: run deliberate provider/course checks.
