import asyncio
import hashlib
import json
import os
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from uuid import uuid4

from .config import get_settings
from .question_history import normalize_question_text


DOCUMENT_STATUSES = {"draft", "queued", "indexing", "indexed", "failed", "deleting"}
FEEDBACK_STATUSES = {"open", "reviewing", "resolved", "dismissed"}
FEEDBACK_CATEGORIES = {"change", "error", "other"}


class VersionConflictError(RuntimeError):
    pass


class AdminStore:
    """Durable single-node admin metadata store.

    SQLite is the source of truth for editable document text, jobs, feedback, and
    the audit trail. Qdrant remains a derived retrieval index.
    """

    _initialization_lock = threading.Lock()
    _initialized_paths: set[str] = set()

    def __init__(self, database_file: str | None = None, media_directory: str | None = None) -> None:
        settings = get_settings()
        self.database_path = Path(database_file or settings.admin_database_file)
        self.media_directory = Path(media_directory or settings.feedback_media_directory)

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def _raw_connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _ensure_initialized_sync(self) -> None:
        key = str(self.database_path.resolve())
        if key in self._initialized_paths and self.database_path.exists():
            return
        with self._initialization_lock:
            if key in self._initialized_paths and self.database_path.exists():
                return
            self._initialize_sync()
            self._initialized_paths.add(key)

    def _connect(self) -> sqlite3.Connection:
        self._ensure_initialized_sync()
        return self._raw_connect()

    def _initialize_sync(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.media_directory.mkdir(parents=True, exist_ok=True)
        with self._raw_connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS knowledge_documents (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    course TEXT NOT NULL,
                    doc_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    version INTEGER NOT NULL DEFAULT 1,
                    published_version INTEGER,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    indexed_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_documents_updated
                    ON knowledge_documents(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_documents_course_status
                    ON knowledge_documents(course, status);

                CREATE TABLE IF NOT EXISTS training_jobs (
                    id TEXT PRIMARY KEY,
                    document_ids TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    total_documents INTEGER NOT NULL,
                    completed_documents INTEGER NOT NULL DEFAULT 0,
                    failed_documents INTEGER NOT NULL DEFAULT 0,
                    total_chunks INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    heartbeat_at TEXT,
                    lease_token TEXT,
                    completed_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_training_jobs_created
                    ON training_jobs(created_at DESC);

                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    whatsapp_message_id TEXT NOT NULL UNIQUE,
                    sender TEXT NOT NULL,
                    profile_name TEXT,
                    category TEXT NOT NULL DEFAULT 'other',
                    message TEXT NOT NULL,
                    attachment_filename TEXT,
                    attachment_mime_type TEXT,
                    attachment_size INTEGER,
                    status TEXT NOT NULL DEFAULT 'open',
                    admin_notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_feedback_status_created
                    ON feedback(status, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_feedback_created
                    ON feedback(created_at);

                CREATE TABLE IF NOT EXISTS feedback_sessions (
                    sender TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_feedback_sessions_expiry
                    ON feedback_sessions(expires_at);

                CREATE TABLE IF NOT EXISTS whatsapp_webhook_events (
                    id TEXT PRIMARY KEY,
                    payload_hash TEXT NOT NULL UNIQUE,
                    payload TEXT NOT NULL,
                    inbound_message_count INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    available_at TEXT NOT NULL,
                    lease_token TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_webhook_events_due
                    ON whatsapp_webhook_events(status, available_at, updated_at);

                CREATE TABLE IF NOT EXISTS admin_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT,
                    details TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_audit_created
                    ON admin_audit_log(created_at DESC);

                CREATE TABLE IF NOT EXISTS usage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    course TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    latency_ms INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_usage_created
                    ON usage_events(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_usage_student_created
                    ON usage_events(student_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS approved_answers (
                    id TEXT PRIMARY KEY,
                    course TEXT NOT NULL,
                    question TEXT NOT NULL,
                    normalized_question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
                    version INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    published_at TEXT,
                    UNIQUE(course, normalized_question)
                );

                CREATE INDEX IF NOT EXISTS idx_approved_answers_status_course
                    ON approved_answers(status, course, updated_at DESC);
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (1, self._now()),
            )
            training_columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(training_jobs)").fetchall()
            }
            if "heartbeat_at" not in training_columns:
                connection.execute("ALTER TABLE training_jobs ADD COLUMN heartbeat_at TEXT")
            if "lease_token" not in training_columns:
                connection.execute("ALTER TABLE training_jobs ADD COLUMN lease_token TEXT")
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (2, self._now()),
            )
            document_columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(knowledge_documents)").fetchall()
            }
            if "published_version" not in document_columns:
                connection.execute("ALTER TABLE knowledge_documents ADD COLUMN published_version INTEGER")
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (3, self._now()),
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (4, self._now()),
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (5, self._now()),
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (6, self._now()),
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (7, self._now()),
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (8, self._now()),
            )
            webhook_columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(whatsapp_webhook_events)").fetchall()
            }
            if "inbound_message_count" not in webhook_columns:
                connection.execute(
                    "ALTER TABLE whatsapp_webhook_events "
                    "ADD COLUMN inbound_message_count INTEGER NOT NULL DEFAULT 0"
                )
                rows = connection.execute(
                    "SELECT id, payload FROM whatsapp_webhook_events"
                ).fetchall()
                for row in rows:
                    try:
                        payload = json.loads(str(row["payload"]))
                    except (TypeError, ValueError):
                        continue
                    count = self._whatsapp_inbound_message_count(payload)
                    if count:
                        connection.execute(
                            "UPDATE whatsapp_webhook_events "
                            "SET inbound_message_count = ? WHERE id = ?",
                            (count, str(row["id"])),
                        )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_webhook_events_inbound_created "
                "ON whatsapp_webhook_events(inbound_message_count, created_at DESC)"
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (9, self._now()),
            )

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    def _audit_sync(
        self,
        connection: sqlite3.Connection,
        action: str,
        entity_type: str,
        entity_id: str | None,
        details: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO admin_audit_log(action, entity_type, entity_id, details, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                action,
                entity_type,
                entity_id,
                json.dumps(details or {}, ensure_ascii=False, separators=(",", ":")),
                self._now(),
            ),
        )

    def _record_audit_sync(
        self,
        action: str,
        entity_type: str,
        entity_id: str | None,
        details: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as connection:
            self._audit_sync(connection, action, entity_type, entity_id, details)

    async def record_audit(
        self,
        action: str,
        entity_type: str,
        entity_id: str | None,
        details: dict[str, Any] | None = None,
    ) -> None:
        await asyncio.to_thread(
            self._record_audit_sync,
            action,
            entity_type,
            entity_id,
            details,
        )

    def _create_approved_answer_sync(self, course: str, question: str, answer: str) -> dict[str, Any]:
        record_id = str(uuid4())
        now = self._now()
        normalized = normalize_question_text(question)
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO approved_answers(
                        id, course, question, normalized_question, answer, status,
                        version, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'draft', 1, ?, ?)
                    """,
                    (record_id, course.upper(), question.strip(), normalized, answer.strip(), now, now),
                )
                self._audit_sync(connection, "approved_answer.created", "approved_answer", record_id, {"course": course.upper()})
                row = connection.execute("SELECT * FROM approved_answers WHERE id = ?", (record_id,)).fetchone()
        except sqlite3.IntegrityError as exc:
            raise VersionConflictError("An approved answer already exists for this course and question") from exc
        return dict(row)

    async def create_approved_answer(self, course: str, question: str, answer: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._create_approved_answer_sync, course, question, answer)

    def _list_approved_answers_sync(self, course: str | None, limit: int, offset: int) -> dict[str, Any]:
        where = "WHERE course = ?" if course else ""
        params: list[Any] = [course.upper()] if course else []
        with self._connect() as connection:
            total = connection.execute(f"SELECT COUNT(*) FROM approved_answers {where}", params).fetchone()[0]
            rows = connection.execute(
                f"SELECT * FROM approved_answers {where} ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
        return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}

    async def list_approved_answers(self, course: str | None = None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        return await asyncio.to_thread(self._list_approved_answers_sync, course, limit, offset)

    def _find_published_answer_sync(self, course: str, question: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM approved_answers
                   WHERE course = ? AND normalized_question = ? AND status = 'published'""",
                (course.upper(), normalize_question_text(question)),
            ).fetchone()
        return self._row(row)

    async def find_published_answer(self, course: str, question: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._find_published_answer_sync, course, question)

    def _update_approved_answer_sync(
        self, record_id: str, course: str, question: str, answer: str, version: int
    ) -> dict[str, Any] | None:
        now = self._now()
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """UPDATE approved_answers SET course = ?, question = ?, normalized_question = ?,
                       answer = ?, status = 'draft', version = version + 1, updated_at = ?, published_at = NULL
                       WHERE id = ? AND version = ?""",
                    (course.upper(), question.strip(), normalize_question_text(question), answer.strip(), now, record_id, version),
                )
                if cursor.rowcount == 0:
                    exists = connection.execute("SELECT 1 FROM approved_answers WHERE id = ?", (record_id,)).fetchone()
                    if exists:
                        raise VersionConflictError("Approved answer changed; refresh and try again")
                    return None
                self._audit_sync(connection, "approved_answer.updated", "approved_answer", record_id, {"course": course.upper()})
                row = connection.execute("SELECT * FROM approved_answers WHERE id = ?", (record_id,)).fetchone()
        except sqlite3.IntegrityError as exc:
            raise VersionConflictError("An approved answer already exists for this course and question") from exc
        return self._row(row)

    async def update_approved_answer(self, record_id: str, course: str, question: str, answer: str, version: int) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._update_approved_answer_sync, record_id, course, question, answer, version)

    def _publish_approved_answer_sync(self, record_id: str) -> dict[str, Any] | None:
        now = self._now()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE approved_answers SET status = 'published', published_at = ?, updated_at = ? WHERE id = ?",
                (now, now, record_id),
            )
            if cursor.rowcount == 0:
                return None
            self._audit_sync(connection, "approved_answer.published", "approved_answer", record_id)
            row = connection.execute("SELECT * FROM approved_answers WHERE id = ?", (record_id,)).fetchone()
        return self._row(row)

    async def publish_approved_answer(self, record_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._publish_approved_answer_sync, record_id)

    def _delete_approved_answer_sync(self, record_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute("SELECT course FROM approved_answers WHERE id = ?", (record_id,)).fetchone()
            if not row:
                return False
            connection.execute("DELETE FROM approved_answers WHERE id = ?", (record_id,))
            self._audit_sync(connection, "approved_answer.deleted", "approved_answer", record_id, {"course": row["course"]})
        return True

    async def delete_approved_answer(self, record_id: str) -> bool:
        return await asyncio.to_thread(self._delete_approved_answer_sync, record_id)

    def _record_usage_sync(
        self,
        student_id: str,
        channel: str,
        course: str,
        mode: str,
        status: str,
        latency_ms: int,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO usage_events(student_id, channel, course, mode, status, latency_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (student_id[:200], channel[:30], course[:20], mode[:40], status[:20], max(0, latency_ms), self._now()),
            )

    async def record_usage(
        self,
        *,
        student_id: str,
        channel: str,
        course: str,
        mode: str,
        status: str,
        latency_ms: int,
    ) -> None:
        await asyncio.to_thread(
            self._record_usage_sync,
            student_id,
            channel,
            course,
            mode,
            status,
            latency_ms,
        )

    def _analytics_sync(self, days: int) -> dict[str, Any]:
        cutoff = (datetime.now(UTC) - timedelta(days=max(1, min(days, 365)))).isoformat()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT student_id, channel, course, mode, status, latency_ms, created_at
                FROM usage_events WHERE created_at >= ? ORDER BY created_at ASC
                """,
                (cutoff,),
            ).fetchall()

        daily: dict[str, int] = {}
        courses: dict[str, int] = {}
        channels: dict[str, int] = {}
        modes: dict[str, int] = {}
        students: dict[str, dict[str, Any]] = {}
        total_latency = 0
        errors = 0
        for row in rows:
            day = str(row["created_at"])[:10]
            daily[day] = daily.get(day, 0) + 1
            course = str(row["course"])
            channel = str(row["channel"])
            mode = str(row["mode"])
            courses[course] = courses.get(course, 0) + 1
            channels[channel] = channels.get(channel, 0) + 1
            modes[mode] = modes.get(mode, 0) + 1
            latency = int(row["latency_ms"] or 0)
            total_latency += latency
            if row["status"] != "success":
                errors += 1
            student_id = str(row["student_id"])
            student = students.setdefault(
                student_id,
                {"student_id": student_id, "requests": 0, "errors": 0, "latency_total": 0, "courses": set(), "last_active": ""},
            )
            student["requests"] += 1
            student["errors"] += 1 if row["status"] != "success" else 0
            student["latency_total"] += latency
            student["courses"].add(course)
            student["last_active"] = max(student["last_active"], str(row["created_at"]))

        student_items = []
        for student in students.values():
            requests = int(student["requests"])
            student_items.append(
                {
                    "student_id": student["student_id"],
                    "requests": requests,
                    "errors": student["errors"],
                    "average_latency_ms": round(student["latency_total"] / requests) if requests else 0,
                    "courses": sorted(student["courses"]),
                    "last_active": student["last_active"],
                }
            )
        student_items.sort(key=lambda item: (-item["requests"], item["student_id"]))
        total = len(rows)
        return {
            "days": days,
            "totals": {
                "requests": total,
                "students": len(students),
                "errors": errors,
                "success_rate": round(((total - errors) / total) * 100, 1) if total else 100.0,
                "average_latency_ms": round(total_latency / total) if total else 0,
            },
            "daily": [{"date": key, "requests": value} for key, value in sorted(daily.items())],
            "courses": [{"label": key, "value": value} for key, value in sorted(courses.items(), key=lambda item: (-item[1], item[0]))],
            "channels": [{"label": key, "value": value} for key, value in sorted(channels.items(), key=lambda item: (-item[1], item[0]))],
            "modes": [{"label": key, "value": value} for key, value in sorted(modes.items(), key=lambda item: (-item[1], item[0]))],
            "students": student_items[:200],
        }

    async def analytics(self, days: int = 30) -> dict[str, Any]:
        return await asyncio.to_thread(self._analytics_sync, days)

    def _create_document_sync(
        self,
        *,
        title: str,
        filename: str,
        course: str,
        doc_type: str,
        content: str,
    ) -> dict[str, Any]:
        document_id = str(uuid4())
        now = self._now()
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO knowledge_documents(
                    id, title, filename, course, doc_type, content, content_hash,
                    status, chunk_count, version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', 0, 1, ?, ?)
                """,
                (document_id, title, filename, course, doc_type, content, content_hash, now, now),
            )
            self._audit_sync(
                connection,
                "document.created",
                "knowledge_document",
                document_id,
                {"filename": filename, "course": course, "doc_type": doc_type},
            )
            row = connection.execute(
                "SELECT * FROM knowledge_documents WHERE id = ?", (document_id,)
            ).fetchone()
        return dict(row)

    async def create_document(self, **values: Any) -> dict[str, Any]:
        return await asyncio.to_thread(self._create_document_sync, **values)

    def _create_documents_sync(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Insert one upload batch in a single transaction."""
        created: list[dict[str, Any]] = []
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for values in documents:
                document_id = str(uuid4())
                now = self._now()
                content = str(values["content"])
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                connection.execute(
                    """
                    INSERT INTO knowledge_documents(
                        id, title, filename, course, doc_type, content, content_hash,
                        status, chunk_count, version, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', 0, 1, ?, ?)
                    """,
                    (
                        document_id,
                        values["title"],
                        values["filename"],
                        values["course"],
                        values["doc_type"],
                        content,
                        content_hash,
                        now,
                        now,
                    ),
                )
                self._audit_sync(
                    connection,
                    "document.created",
                    "knowledge_document",
                    document_id,
                    {
                        "filename": values["filename"],
                        "course": values["course"],
                        "doc_type": values["doc_type"],
                    },
                )
                row = connection.execute(
                    "SELECT * FROM knowledge_documents WHERE id = ?",
                    (document_id,),
                ).fetchone()
                created.append(dict(row))
        return created

    async def create_documents(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._create_documents_sync, documents)

    def _list_documents_sync(
        self,
        *,
        search: str = "",
        course: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if search:
            clauses.append("(title LIKE ? OR filename LIKE ?)")
            pattern = f"%{search}%"
            parameters.extend([pattern, pattern])
        if course:
            clauses.append("course = ?")
            parameters.append(course)
        if status:
            clauses.append("status = ?")
            parameters.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM knowledge_documents {where}", parameters
            ).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT id, title, filename, course, doc_type, status, chunk_count,
                       version, published_version, error_message, created_at, updated_at, indexed_at,
                       length(content) AS character_count
                FROM knowledge_documents
                {where}
                ORDER BY updated_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                [*parameters, limit, offset],
            ).fetchall()
        return {"items": [dict(row) for row in rows], "total": total}

    async def list_documents(self, **filters: Any) -> dict[str, Any]:
        return await asyncio.to_thread(self._list_documents_sync, **filters)

    def _list_published_source_revisions_sync(self) -> list[str]:
        """Return the only document revisions that retrieval is allowed to expose."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, published_version
                FROM knowledge_documents
                WHERE published_version IS NOT NULL AND status <> 'deleting'
                """
            ).fetchall()
        return [f"{row['id']}:{int(row['published_version'])}" for row in rows]

    async def list_published_source_revisions(self) -> list[str]:
        return await asyncio.to_thread(self._list_published_source_revisions_sync)

    def _get_document_sync(self, document_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            return self._row(
                connection.execute(
                    "SELECT * FROM knowledge_documents WHERE id = ?", (document_id,)
                ).fetchone()
            )

    async def get_document(self, document_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_document_sync, document_id)

    def _find_document_sync(self, filename: str, course: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            return self._row(
                connection.execute(
                    """
                    SELECT * FROM knowledge_documents
                    WHERE filename = ? AND course = ?
                    ORDER BY created_at LIMIT 1
                    """,
                    (filename, course),
                ).fetchone()
            )

    async def find_document(self, filename: str, course: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._find_document_sync, filename, course)

    def _update_document_sync(
        self,
        document_id: str,
        *,
        title: str,
        course: str,
        doc_type: str,
        content: str,
        expected_version: int | None,
    ) -> dict[str, Any] | None:
        now = self._now()
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT version, status FROM knowledge_documents WHERE id = ?", (document_id,)
            ).fetchone()
            if current is None:
                return None
            if current["status"] in {"queued", "indexing", "deleting"}:
                raise VersionConflictError("The document is busy and cannot be edited")
            if expected_version is not None and int(current["version"]) != expected_version:
                raise VersionConflictError("The document changed after it was opened")
            connection.execute(
                """
                UPDATE knowledge_documents
                SET title = ?, course = ?, doc_type = ?, content = ?, content_hash = ?,
                    status = 'draft', error_message = NULL, version = version + 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (title, course, doc_type, content, content_hash, now, document_id),
            )
            self._audit_sync(
                connection,
                "document.updated",
                "knowledge_document",
                document_id,
                {"course": course, "doc_type": doc_type},
            )
            row = connection.execute(
                "SELECT * FROM knowledge_documents WHERE id = ?", (document_id,)
            ).fetchone()
        return dict(row)

    async def update_document(self, document_id: str, **values: Any) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._update_document_sync, document_id, **values)

    def _prepare_document_delete_sync(self, document_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM knowledge_documents WHERE id = ?", (document_id,)
            ).fetchone()
            if row is None:
                return None
            if row["status"] in {"queued", "indexing", "deleting"}:
                raise VersionConflictError("The document is busy and cannot be deleted")
            connection.execute(
                "UPDATE knowledge_documents SET status = 'deleting', updated_at = ? WHERE id = ?",
                (self._now(), document_id),
            )
            return dict(row)

    async def prepare_document_delete(self, document_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._prepare_document_delete_sync, document_id)

    def _delete_document_sync(self, document_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT title FROM knowledge_documents WHERE id = ?", (document_id,)
            ).fetchone()
            if row is None:
                return False
            connection.execute("DELETE FROM knowledge_documents WHERE id = ?", (document_id,))
            self._audit_sync(
                connection,
                "document.deleted",
                "knowledge_document",
                document_id,
                {"title": row["title"]},
            )
        return True

    async def delete_document(self, document_id: str) -> bool:
        return await asyncio.to_thread(self._delete_document_sync, document_id)

    def _list_deleting_documents_sync(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_documents WHERE status = 'deleting' ORDER BY updated_at"
            ).fetchall()
        return [dict(row) for row in rows]

    async def list_deleting_documents(self) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._list_deleting_documents_sync)

    def _set_document_status_sync(
        self,
        document_id: str,
        status: str,
        *,
        chunk_count: int | None = None,
        error_message: str | None = None,
    ) -> None:
        if status not in DOCUMENT_STATUSES:
            raise ValueError("Invalid document status")
        now = self._now()
        indexed_at = now if status == "indexed" else None
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE knowledge_documents
                SET status = ?,
                    chunk_count = COALESCE(?, chunk_count),
                    error_message = ?,
                    published_version = CASE WHEN ? = 'indexed' THEN version ELSE published_version END,
                    indexed_at = COALESCE(?, indexed_at),
                    updated_at = ?
                WHERE id = ?
                """,
                (status, chunk_count, error_message, status, indexed_at, now, document_id),
            )

    async def set_document_status(self, document_id: str, status: str, **values: Any) -> None:
        await asyncio.to_thread(self._set_document_status_sync, document_id, status, **values)

    def _set_document_status_for_job_sync(
        self,
        document_id: str,
        status: str,
        *,
        job_id: str,
        lease_token: str,
        chunk_count: int | None = None,
        error_message: str | None = None,
    ) -> bool:
        if status not in DOCUMENT_STATUSES:
            raise ValueError("Invalid document status")
        now = self._now()
        indexed_at = now if status == "indexed" else None
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            lease = connection.execute(
                """
                SELECT 1 FROM training_jobs
                WHERE id = ? AND status = 'running' AND lease_token = ?
                """,
                (job_id, lease_token),
            ).fetchone()
            if lease is None:
                return False
            cursor = connection.execute(
                """
                UPDATE knowledge_documents
                SET status = ?, chunk_count = COALESCE(?, chunk_count), error_message = ?,
                    published_version = CASE WHEN ? = 'indexed' THEN version ELSE published_version END,
                    indexed_at = COALESCE(?, indexed_at), updated_at = ?
                WHERE id = ? AND status <> 'deleting'
                """,
                (status, chunk_count, error_message, status, indexed_at, now, document_id),
            )
        return cursor.rowcount == 1

    async def set_document_status_for_job(
        self,
        document_id: str,
        status: str,
        **values: Any,
    ) -> bool:
        return await asyncio.to_thread(
            self._set_document_status_for_job_sync,
            document_id,
            status,
            **values,
        )

    def _publish_document_revision_sync(
        self,
        document_id: str,
        *,
        expected_version: int,
        chunk_count: int,
    ) -> None:
        now = self._now()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE knowledge_documents
                SET status = 'indexed', chunk_count = ?, error_message = NULL,
                    published_version = ?, indexed_at = ?, updated_at = ?
                WHERE id = ? AND version = ? AND status = 'indexing'
                """,
                (chunk_count, expected_version, now, now, document_id, expected_version),
            )
            if cursor.rowcount != 1:
                raise VersionConflictError("The document changed while its index was being published")
            self._audit_sync(
                connection,
                "document.published",
                "knowledge_document",
                document_id,
                {"version": expected_version, "chunk_count": chunk_count},
            )

    async def publish_document_revision(
        self,
        document_id: str,
        *,
        expected_version: int,
        chunk_count: int,
    ) -> None:
        await asyncio.to_thread(
            self._publish_document_revision_sync,
            document_id,
            expected_version=expected_version,
            chunk_count=chunk_count,
        )

    def _publish_document_revision_for_job_sync(
        self,
        document_id: str,
        *,
        expected_version: int,
        chunk_count: int,
        job_id: str,
        lease_token: str,
    ) -> bool:
        now = self._now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            lease = connection.execute(
                """
                SELECT 1 FROM training_jobs
                WHERE id = ? AND status = 'running' AND lease_token = ?
                """,
                (job_id, lease_token),
            ).fetchone()
            if lease is None:
                return False
            cursor = connection.execute(
                """
                UPDATE knowledge_documents
                SET status = 'indexed', chunk_count = ?, error_message = NULL,
                    published_version = ?, indexed_at = ?, updated_at = ?
                WHERE id = ? AND version = ? AND status = 'indexing'
                """,
                (chunk_count, expected_version, now, now, document_id, expected_version),
            )
            if cursor.rowcount != 1:
                raise VersionConflictError("The document changed while its index was being published")
            self._audit_sync(
                connection,
                "document.published",
                "knowledge_document",
                document_id,
                {"version": expected_version, "chunk_count": chunk_count, "job_id": job_id},
            )
        return True

    async def publish_document_revision_for_job(
        self,
        document_id: str,
        *,
        expected_version: int,
        chunk_count: int,
        job_id: str,
        lease_token: str,
    ) -> bool:
        return await asyncio.to_thread(
            self._publish_document_revision_for_job_sync,
            document_id,
            expected_version=expected_version,
            chunk_count=chunk_count,
            job_id=job_id,
            lease_token=lease_token,
        )

    def _create_training_job_sync(self, document_ids: list[str]) -> dict[str, Any]:
        job_id = str(uuid4())
        now = self._now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            placeholders = ",".join("?" for _ in document_ids)
            rows = connection.execute(
                f"SELECT id, status FROM knowledge_documents WHERE id IN ({placeholders})",
                document_ids,
            ).fetchall()
            existing = {str(row["id"]) for row in rows}
            missing = [document_id for document_id in document_ids if document_id not in existing]
            if missing:
                raise KeyError(",".join(missing))
            active = [
                str(row["id"])
                for row in rows
                if row["status"] in {"queued", "indexing", "deleting"}
            ]
            if active:
                raise VersionConflictError(
                    "A training job is already active for: " + ", ".join(active)
                )
            connection.execute(
                """
                INSERT INTO training_jobs(
                    id, document_ids, status, total_documents, created_at
                ) VALUES (?, ?, 'queued', ?, ?)
                """,
                (job_id, json.dumps(document_ids), len(document_ids), now),
            )
            for document_id in document_ids:
                connection.execute(
                    "UPDATE knowledge_documents SET status = 'queued', error_message = NULL WHERE id = ?",
                    (document_id,),
                )
            self._audit_sync(
                connection,
                "training.queued",
                "training_job",
                job_id,
                {"document_ids": document_ids},
            )
            row = connection.execute("SELECT * FROM training_jobs WHERE id = ?", (job_id,)).fetchone()
        result = dict(row)
        result["document_ids"] = json.loads(result["document_ids"])
        return result

    async def create_training_job(self, document_ids: list[str]) -> dict[str, Any]:
        return await asyncio.to_thread(self._create_training_job_sync, document_ids)

    def _claim_training_job_sync(self, job_id: str) -> dict[str, Any] | None:
        now = self._now()
        lease_token = str(uuid4())
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE training_jobs
                SET status = 'running', started_at = ?, heartbeat_at = ?, lease_token = ?
                WHERE id = ? AND status = 'queued'
                """,
                (now, now, lease_token, job_id),
            )
            if cursor.rowcount != 1:
                return None
            row = connection.execute("SELECT * FROM training_jobs WHERE id = ?", (job_id,)).fetchone()
        result = dict(row)
        result["document_ids"] = json.loads(result["document_ids"])
        return result

    async def claim_training_job(self, job_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._claim_training_job_sync, job_id)

    def _update_training_progress_sync(
        self,
        job_id: str,
        *,
        completed_delta: int = 0,
        failed_delta: int = 0,
        chunk_delta: int = 0,
        lease_token: str | None = None,
    ) -> bool:
        lease_clause = " AND status = 'running' AND lease_token = ?" if lease_token else ""
        parameters: list[Any] = [
            completed_delta,
            failed_delta,
            chunk_delta,
            self._now(),
            job_id,
        ]
        if lease_token:
            parameters.append(lease_token)
        with self._connect() as connection:
            cursor = connection.execute(
                f"""
                UPDATE training_jobs
                SET completed_documents = completed_documents + ?,
                    failed_documents = failed_documents + ?,
                    total_chunks = total_chunks + ?,
                    heartbeat_at = ?
                WHERE id = ?{lease_clause}
                """,
                parameters,
            )
        return cursor.rowcount == 1

    async def update_training_progress(self, job_id: str, **values: Any) -> bool:
        return await asyncio.to_thread(self._update_training_progress_sync, job_id, **values)

    def _touch_training_job_sync(self, job_id: str, lease_token: str | None = None) -> bool:
        lease_clause = " AND lease_token = ?" if lease_token else ""
        parameters = [self._now(), job_id]
        if lease_token:
            parameters.append(lease_token)
        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE training_jobs SET heartbeat_at = ? WHERE id = ? AND status = 'running'{lease_clause}",
                parameters,
            )
        return cursor.rowcount == 1

    async def touch_training_job(self, job_id: str, lease_token: str | None = None) -> bool:
        return await asyncio.to_thread(self._touch_training_job_sync, job_id, lease_token)

    def _requeue_training_job_sync(self, job_id: str, lease_token: str | None = None) -> bool:
        """Return an interrupted running job to a clean, idempotent queued state."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            job = connection.execute(
                "SELECT document_ids, lease_token FROM training_jobs WHERE id = ? AND status = 'running'",
                (job_id,),
            ).fetchone()
            if job is None or (lease_token is not None and job["lease_token"] != lease_token):
                return False
            document_ids = json.loads(job["document_ids"])
            for document_id in document_ids:
                connection.execute(
                    """
                    UPDATE knowledge_documents
                    SET status = 'queued', error_message = NULL, updated_at = ?
                    WHERE id = ? AND status IN ('queued', 'indexing', 'failed', 'indexed')
                    """,
                    (self._now(), document_id),
                )
            connection.execute(
                """
                UPDATE training_jobs
                SET status = 'queued', completed_documents = 0, failed_documents = 0,
                    total_chunks = 0, error_message = NULL, started_at = NULL,
                    heartbeat_at = NULL, lease_token = NULL, completed_at = NULL
                WHERE id = ? AND status = 'running' AND lease_token IS ?
                """,
                (job_id, job["lease_token"]),
            )
            self._audit_sync(
                connection,
                "training.requeued",
                "training_job",
                job_id,
                {"reason": "worker_interrupted"},
            )
        return True

    async def requeue_training_job(self, job_id: str, lease_token: str | None = None) -> bool:
        return await asyncio.to_thread(self._requeue_training_job_sync, job_id, lease_token)

    def _finish_training_job_sync(
        self,
        job_id: str,
        error_message: str | None = None,
        lease_token: str | None = None,
    ) -> bool:
        now = self._now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            job = connection.execute(
                "SELECT failed_documents, total_documents, status, lease_token FROM training_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if (
                job is None
                or job["status"] != "running"
                or (lease_token is not None and job["lease_token"] != lease_token)
            ):
                return False
            failed = int(job["failed_documents"])
            total = int(job["total_documents"])
            if error_message or failed >= total:
                final_status = "failed"
            elif failed:
                final_status = "partial"
            else:
                final_status = "completed"
            connection.execute(
                """
                UPDATE training_jobs
                SET status = ?, error_message = ?, completed_at = ?, heartbeat_at = ?, lease_token = NULL
                WHERE id = ? AND status = 'running' AND lease_token IS ?
                """,
                (final_status, error_message, now, now, job_id, job["lease_token"]),
            )
            self._audit_sync(
                connection,
                f"training.{final_status}",
                "training_job",
                job_id,
                {"failed_documents": failed, "total_documents": total},
            )
        return True

    async def finish_training_job(
        self,
        job_id: str,
        error_message: str | None = None,
        lease_token: str | None = None,
    ) -> bool:
        return await asyncio.to_thread(
            self._finish_training_job_sync,
            job_id,
            error_message,
            lease_token,
        )

    def _get_training_job_sync(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM training_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["document_ids"] = json.loads(item["document_ids"])
        item.pop("lease_token", None)
        return item

    async def get_training_job(self, job_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_training_job_sync, job_id)

    def _list_training_jobs_sync(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self._connect() as connection:
            total = connection.execute("SELECT COUNT(*) FROM training_jobs").fetchone()[0]
            rows = connection.execute(
                "SELECT * FROM training_jobs ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["document_ids"] = json.loads(item["document_ids"])
            item.pop("lease_token", None)
            items.append(item)
        return {"items": items, "total": total}

    async def list_training_jobs(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        return await asyncio.to_thread(self._list_training_jobs_sync, limit, offset)

    def _recover_training_jobs_sync(self) -> dict[str, list[str]]:
        """Requeue only jobs whose worker lease is stale, then replay them idempotently."""
        cutoff = (
            datetime.now(UTC) - timedelta(seconds=get_settings().training_lease_timeout_seconds)
        ).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            stale = connection.execute(
                """
                SELECT id, document_ids FROM training_jobs
                WHERE status = 'running' AND COALESCE(heartbeat_at, started_at, created_at) < ?
                """,
                (cutoff,),
            ).fetchall()
            for job in stale:
                document_ids = json.loads(job["document_ids"])
                for document_id in document_ids:
                    connection.execute(
                        """
                        UPDATE knowledge_documents
                        SET status = 'queued', error_message = NULL
                        WHERE id = ? AND status <> 'deleting'
                        """,
                        (document_id,),
                    )
                connection.execute(
                    """
                    UPDATE training_jobs
                    SET status = 'queued', completed_documents = 0, failed_documents = 0,
                        total_chunks = 0, error_message = NULL, started_at = NULL,
                        heartbeat_at = NULL, lease_token = NULL, completed_at = NULL
                    WHERE id = ?
                    """,
                    (job["id"],),
                )
            rows = connection.execute(
                "SELECT id FROM training_jobs WHERE status = 'queued' ORDER BY created_at"
            ).fetchall()
        return {
            "queued": [str(row["id"]) for row in rows],
            "recovered": [str(row["id"]) for row in stale],
        }

    async def recover_training_jobs(self) -> list[str]:
        result = await asyncio.to_thread(self._recover_training_jobs_sync)
        return result["queued"]

    async def recover_training_jobs_detailed(self) -> dict[str, list[str]]:
        return await asyncio.to_thread(self._recover_training_jobs_sync)

    @staticmethod
    def _whatsapp_inbound_message_count(payload: dict[str, Any]) -> int:
        count = 0
        for entry in payload.get("entry") or []:
            if not isinstance(entry, dict):
                continue
            for change in entry.get("changes") or []:
                if not isinstance(change, dict):
                    continue
                value = change.get("value") or {}
                if not isinstance(value, dict):
                    continue
                count += sum(
                    1
                    for message in value.get("messages") or []
                    if isinstance(message, dict)
                    and str(message.get("id") or "").strip()
                    and str(message.get("from") or "").strip()
                )
        return count

    def _enqueue_whatsapp_webhook_sync(self, payload: dict[str, Any]) -> dict[str, Any]:
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        payload_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        inbound_message_count = self._whatsapp_inbound_message_count(payload)
        event_id = str(uuid4())
        now = self._now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO whatsapp_webhook_events(
                    id, payload_hash, payload, inbound_message_count,
                    status, available_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)
                """,
                (event_id, payload_hash, serialized, inbound_message_count, now, now, now),
            )
            row = connection.execute(
                "SELECT * FROM whatsapp_webhook_events WHERE payload_hash = ?",
                (payload_hash,),
            ).fetchone()
        result = dict(row)
        result["payload"] = json.loads(result["payload"])
        result.pop("lease_token", None)
        return result

    async def enqueue_whatsapp_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._enqueue_whatsapp_webhook_sync, payload)

    def _whatsapp_queue_summary_sync(self) -> dict[str, Any]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS count FROM whatsapp_webhook_events GROUP BY status"
            ).fetchall()
            latest = connection.execute(
                """SELECT status, attempts, last_error, created_at, updated_at, completed_at
                   FROM whatsapp_webhook_events ORDER BY created_at DESC, id DESC LIMIT 1"""
            ).fetchone()
            latest_inbound_message_at = connection.execute(
                """SELECT MAX(created_at) AS created_at
                   FROM whatsapp_webhook_events WHERE inbound_message_count > 0"""
            ).fetchone()["created_at"]
        counts = {status: 0 for status in ("pending", "processing", "failed", "completed", "dead_letter")}
        counts.update({str(row["status"]): int(row["count"]) for row in rows})
        return {
            "counts": counts,
            "latest_event": self._row(latest),
            "latest_inbound_message_at": latest_inbound_message_at,
        }

    async def whatsapp_queue_summary(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._whatsapp_queue_summary_sync)

    def _claim_whatsapp_webhook_sync(self, event_id: str) -> dict[str, Any] | None:
        now_dt = datetime.now(UTC)
        now = now_dt.isoformat()
        max_attempts = max(1, int(get_settings().whatsapp_webhook_max_attempts))
        stale_cutoff = (
            now_dt - timedelta(seconds=get_settings().whatsapp_webhook_lease_timeout_seconds)
        ).isoformat()
        lease_token = str(uuid4())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE whatsapp_webhook_events
                SET status = 'processing', attempts = attempts + 1, lease_token = ?,
                    last_error = NULL, updated_at = ?
                WHERE id = ? AND (
                    (status IN ('pending', 'failed') AND available_at <= ?)
                    OR (status = 'processing' AND updated_at < ?)
                ) AND attempts < ?
                """,
                (lease_token, now, event_id, now, stale_cutoff, max_attempts),
            )
            if cursor.rowcount != 1:
                return None
            row = connection.execute(
                "SELECT * FROM whatsapp_webhook_events WHERE id = ?",
                (event_id,),
            ).fetchone()
        result = dict(row)
        result["payload"] = json.loads(result["payload"])
        return result

    async def claim_whatsapp_webhook(self, event_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._claim_whatsapp_webhook_sync, event_id)

    def _touch_whatsapp_webhook_sync(self, event_id: str, lease_token: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE whatsapp_webhook_events SET updated_at = ?
                WHERE id = ? AND status = 'processing' AND lease_token = ?
                """,
                (self._now(), event_id, lease_token),
            )
        return cursor.rowcount == 1

    async def touch_whatsapp_webhook(self, event_id: str, lease_token: str) -> bool:
        return await asyncio.to_thread(
            self._touch_whatsapp_webhook_sync,
            event_id,
            lease_token,
        )

    def _finish_whatsapp_webhook_sync(
        self,
        event_id: str,
        lease_token: str,
        error_message: str | None,
        retry_after_seconds: int | None,
    ) -> bool:
        now_dt = datetime.now(UTC)
        now = now_dt.isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT attempts FROM whatsapp_webhook_events
                WHERE id = ? AND status = 'processing' AND lease_token = ?
                """,
                (event_id, lease_token),
            ).fetchone()
            if row is None:
                return False
            if error_message is None:
                connection.execute(
                    """
                    UPDATE whatsapp_webhook_events
                    SET status = 'completed', lease_token = NULL, last_error = NULL,
                        updated_at = ?, completed_at = ?
                    WHERE id = ? AND lease_token = ?
                    """,
                    (now, now, event_id, lease_token),
                )
            else:
                attempts = int(row["attempts"])
                if attempts >= max(1, int(get_settings().whatsapp_webhook_max_attempts)):
                    connection.execute(
                        """
                        UPDATE whatsapp_webhook_events
                        SET status = 'dead_letter', lease_token = NULL, last_error = ?,
                            updated_at = ?, completed_at = ?
                        WHERE id = ? AND lease_token = ?
                        """,
                        (error_message[:1000], now, now, event_id, lease_token),
                    )
                else:
                    delay = (
                        max(1, min(3600, int(retry_after_seconds)))
                        if retry_after_seconds is not None
                        else min(300, 2 ** min(attempts, 8))
                    )
                    available_at = (now_dt + timedelta(seconds=delay)).isoformat()
                    connection.execute(
                        """
                        UPDATE whatsapp_webhook_events
                        SET status = 'failed', lease_token = NULL, last_error = ?,
                            available_at = ?, updated_at = ?
                        WHERE id = ? AND lease_token = ?
                        """,
                        (error_message[:1000], available_at, now, event_id, lease_token),
                    )
        return True

    async def finish_whatsapp_webhook(
        self,
        event_id: str,
        lease_token: str,
        error_message: str | None = None,
        retry_after_seconds: int | None = None,
    ) -> bool:
        return await asyncio.to_thread(
            self._finish_whatsapp_webhook_sync,
            event_id,
            lease_token,
            error_message,
            retry_after_seconds,
        )

    def _due_whatsapp_webhooks_sync(self, limit: int = 25) -> dict[str, list[str]]:
        now_dt = datetime.now(UTC)
        now = now_dt.isoformat()
        stale_cutoff = (
            now_dt - timedelta(seconds=get_settings().whatsapp_webhook_lease_timeout_seconds)
        ).isoformat()
        retention_cutoff = (now_dt - timedelta(days=7)).isoformat()
        max_attempts = max(1, int(get_settings().whatsapp_webhook_max_attempts))
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM whatsapp_webhook_events
                WHERE status IN ('completed', 'dead_letter') AND completed_at < ?
                """,
                (retention_cutoff,),
            )
            connection.execute(
                """
                UPDATE whatsapp_webhook_events
                SET status = 'dead_letter', lease_token = NULL,
                    last_error = COALESCE(last_error, 'Webhook worker exceeded its retry limit'),
                    updated_at = ?, completed_at = ?
                WHERE attempts >= ? AND (
                    (status IN ('pending', 'failed') AND available_at <= ?)
                    OR (status = 'processing' AND updated_at < ?)
                )
                """,
                (now, now, max_attempts, now, stale_cutoff),
            )
            rows = connection.execute(
                """
                SELECT id, status FROM whatsapp_webhook_events
                WHERE (
                    (status IN ('pending', 'failed') AND available_at <= ?)
                    OR (status = 'processing' AND updated_at < ?)
                ) AND attempts < ?
                ORDER BY available_at, created_at, id
                LIMIT ?
                """,
                (now, stale_cutoff, max_attempts, limit),
            ).fetchall()
        return {
            "due": [str(row["id"]) for row in rows],
            "recovered": [str(row["id"]) for row in rows if row["status"] == "processing"],
        }

    async def due_whatsapp_webhooks(self, limit: int = 25) -> list[str]:
        result = await asyncio.to_thread(self._due_whatsapp_webhooks_sync, limit)
        return result["due"]

    async def due_whatsapp_webhooks_detailed(self, limit: int = 25) -> dict[str, list[str]]:
        return await asyncio.to_thread(self._due_whatsapp_webhooks_sync, limit)

    def _get_feedback_session_sync(self, sender: str) -> str | None:
        now = self._now()
        with self._connect() as connection:
            connection.execute("DELETE FROM feedback_sessions WHERE expires_at <= ?", (now,))
            row = connection.execute(
                "SELECT state FROM feedback_sessions WHERE sender = ? AND expires_at > ?",
                (sender, now),
            ).fetchone()
        return str(row["state"]) if row is not None else None

    async def get_feedback_session(self, sender: str) -> str | None:
        return await asyncio.to_thread(self._get_feedback_session_sync, sender)

    def _set_feedback_session_sync(self, sender: str, state: str, ttl_seconds: int) -> None:
        now = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO feedback_sessions(sender, state, expires_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(sender) DO UPDATE SET
                    state = excluded.state,
                    expires_at = excluded.expires_at,
                    updated_at = excluded.updated_at
                """,
                (
                    sender,
                    state,
                    (now + timedelta(seconds=ttl_seconds)).isoformat(),
                    now.isoformat(),
                ),
            )

    async def set_feedback_session(self, sender: str, state: str, ttl_seconds: int) -> None:
        await asyncio.to_thread(self._set_feedback_session_sync, sender, state, ttl_seconds)

    def _clear_feedback_session_sync(self, sender: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM feedback_sessions WHERE sender = ?", (sender,))

    async def clear_feedback_session(self, sender: str) -> None:
        await asyncio.to_thread(self._clear_feedback_session_sync, sender)

    def _purge_expired_feedback_sync(self) -> int:
        retention_days = max(1, int(get_settings().feedback_retention_days))
        now = datetime.now(UTC)
        cutoff = (now - timedelta(days=retention_days)).isoformat()
        orphan_cutoff = now - timedelta(hours=1)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT id, attachment_filename FROM feedback WHERE created_at < ?",
                (cutoff,),
            ).fetchall()
            if rows:
                connection.execute("DELETE FROM feedback WHERE created_at < ?", (cutoff,))
                self._audit_sync(
                    connection,
                    "feedback.retention_purge",
                    "feedback",
                    None,
                    {"count": len(rows), "retention_days": retention_days},
                )
            live_attachments = {
                str(row["attachment_filename"])
                for row in connection.execute(
                    "SELECT attachment_filename FROM feedback WHERE attachment_filename IS NOT NULL"
                ).fetchall()
            }
        media_root = self.media_directory.resolve()
        expired_attachments = {
            str(row["attachment_filename"])
            for row in rows
            if row["attachment_filename"]
        }
        for candidate in media_root.iterdir():
            if not candidate.is_file() or candidate.suffix.casefold() not in {".jpg", ".png"}:
                continue
            modified_at = datetime.fromtimestamp(candidate.stat().st_mtime, UTC)
            expired = candidate.name in expired_attachments
            orphaned = candidate.name not in live_attachments and modified_at < orphan_cutoff
            if expired or orphaned:
                try:
                    candidate.unlink(missing_ok=True)
                except OSError:
                    # A later maintenance sweep retries transient filesystem failures.
                    continue
        return len(rows)

    async def purge_expired_feedback(self) -> int:
        return await asyncio.to_thread(self._purge_expired_feedback_sync)

    @staticmethod
    def _detect_feedback_category(message: str) -> str:
        normalized = message.casefold()
        if any(word in normalized for word in ("error", "bug", "wrong", "failed", "issue", "problem")):
            return "error"
        if any(word in normalized for word in ("change", "update", "improve", "suggest", "request")):
            return "change"
        return "other"

    @staticmethod
    def _validated_image_extension(image_bytes: bytes, mime_type: str) -> str:
        normalized = mime_type.split(";", 1)[0].strip().lower()
        if normalized in {"image/jpeg", "image/jpg"} and image_bytes.startswith(b"\xff\xd8\xff"):
            return ".jpg"
        if normalized == "image/png" and image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return ".png"
        raise ValueError("Feedback screenshots must be valid JPEG or PNG images")

    def _save_attachment_sync(self, feedback_id: str, image_bytes: bytes, mime_type: str) -> str:
        extension = self._validated_image_extension(image_bytes, mime_type)
        target = self.media_directory / f"{feedback_id}{extension}"
        self.media_directory.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("wb", dir=self.media_directory, delete=False) as handle:
            handle.write(image_bytes)
            temporary = Path(handle.name)
        os.replace(temporary, target)
        return target.name

    def _create_feedback_sync(
        self,
        *,
        whatsapp_message_id: str,
        sender: str,
        profile_name: str | None,
        message: str,
        image_bytes: bytes | None,
        mime_type: str | None,
    ) -> dict[str, Any]:
        feedback_id = str(uuid4())
        now = self._now()
        settings = get_settings()
        normalized_message = " ".join(message.strip().split())[:6000]
        if not normalized_message:
            normalized_message = "Screenshot feedback"
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM feedback WHERE whatsapp_message_id = ?", (whatsapp_message_id,)
            ).fetchone()
            if existing is not None:
                return dict(existing)
            since = (datetime.now(UTC) - timedelta(days=1)).isoformat()
            recent_count = connection.execute(
                "SELECT COUNT(*) FROM feedback WHERE sender = ? AND created_at >= ?",
                (sender, since),
            ).fetchone()[0]
            if recent_count >= settings.feedback_max_per_sender_per_day:
                raise ValueError("Daily feedback limit reached for this WhatsApp number")
            used_storage = connection.execute(
                "SELECT COALESCE(SUM(attachment_size), 0) FROM feedback"
            ).fetchone()[0]
            incoming_size = len(image_bytes) if image_bytes is not None else 0
            if int(used_storage) + incoming_size > settings.feedback_max_storage_bytes:
                raise ValueError("Feedback screenshot storage limit reached")

        attachment_filename = None
        attachment_size = None
        if image_bytes is not None:
            attachment_filename = self._save_attachment_sync(
                feedback_id, image_bytes, mime_type or "application/octet-stream"
            )
            attachment_size = len(image_bytes)
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO feedback(
                        id, whatsapp_message_id, sender, profile_name, category, message,
                        attachment_filename, attachment_mime_type, attachment_size,
                        status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
                    """,
                    (
                        feedback_id,
                        whatsapp_message_id,
                        sender,
                        (profile_name or "")[:200] or None,
                        self._detect_feedback_category(normalized_message),
                        normalized_message,
                        attachment_filename,
                        mime_type if attachment_filename else None,
                        attachment_size,
                        now,
                        now,
                    ),
                )
                self._audit_sync(
                    connection,
                    "feedback.received",
                    "feedback",
                    feedback_id,
                    {"has_attachment": bool(attachment_filename)},
                )
                row = connection.execute("SELECT * FROM feedback WHERE id = ?", (feedback_id,)).fetchone()
            return dict(row)
        except sqlite3.IntegrityError:
            if attachment_filename:
                (self.media_directory / attachment_filename).unlink(missing_ok=True)
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM feedback WHERE whatsapp_message_id = ?", (whatsapp_message_id,)
                ).fetchone()
            if row is None:
                raise
            return dict(row)

    async def create_feedback(self, **values: Any) -> dict[str, Any]:
        return await asyncio.to_thread(self._create_feedback_sync, **values)

    def _list_feedback_sync(
        self,
        *,
        status: str | None = None,
        category: str | None = None,
        search: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if status:
            clauses.append("status = ?")
            parameters.append(status)
        if category:
            clauses.append("category = ?")
            parameters.append(category)
        if search:
            clauses.append(
                "(message LIKE ? OR sender LIKE ? OR profile_name LIKE ? "
                "OR id LIKE ? OR whatsapp_message_id LIKE ?)"
            )
            pattern = f"%{search}%"
            parameters.extend([pattern, pattern, pattern, pattern, pattern])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            total = connection.execute(f"SELECT COUNT(*) FROM feedback {where}", parameters).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT id, sender, profile_name, category, message, attachment_filename,
                       attachment_mime_type, attachment_size, status, admin_notes,
                       created_at, updated_at
                FROM feedback {where}
                ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?
                """,
                [*parameters, limit, offset],
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["has_attachment"] = bool(item.pop("attachment_filename"))
            items.append(item)
        return {"items": items, "total": total}

    async def list_feedback(self, **filters: Any) -> dict[str, Any]:
        return await asyncio.to_thread(self._list_feedback_sync, **filters)

    def _get_feedback_sync(self, feedback_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            return self._row(
                connection.execute("SELECT * FROM feedback WHERE id = ?", (feedback_id,)).fetchone()
            )

    async def get_feedback(self, feedback_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_feedback_sync, feedback_id)

    def _update_feedback_sync(
        self,
        feedback_id: str,
        *,
        status: str,
        category: str,
        admin_notes: str,
    ) -> dict[str, Any] | None:
        if status not in FEEDBACK_STATUSES or category not in FEEDBACK_CATEGORIES:
            raise ValueError("Invalid feedback status or category")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE feedback SET status = ?, category = ?, admin_notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, category, admin_notes[:6000], self._now(), feedback_id),
            )
            if cursor.rowcount != 1:
                return None
            self._audit_sync(
                connection,
                "feedback.updated",
                "feedback",
                feedback_id,
                {"status": status, "category": category},
            )
            row = connection.execute("SELECT * FROM feedback WHERE id = ?", (feedback_id,)).fetchone()
        result = dict(row)
        result["has_attachment"] = bool(result.pop("attachment_filename"))
        return result

    async def update_feedback(self, feedback_id: str, **values: Any) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._update_feedback_sync, feedback_id, **values)

    def attachment_path(self, feedback: dict[str, Any]) -> Path | None:
        filename = feedback.get("attachment_filename")
        if not filename:
            return None
        root = self.media_directory.resolve()
        candidate = (root / str(filename)).resolve()
        if candidate.parent != root or not candidate.is_file():
            return None
        return candidate

    def _overview_sync(self) -> dict[str, Any]:
        with self._connect() as connection:
            documents = connection.execute("SELECT COUNT(*) FROM knowledge_documents").fetchone()[0]
            indexed_documents = connection.execute(
                "SELECT COUNT(*) FROM knowledge_documents WHERE status = 'indexed'"
            ).fetchone()[0]
            open_feedback = connection.execute(
                "SELECT COUNT(*) FROM feedback WHERE status IN ('open', 'reviewing')"
            ).fetchone()[0]
            active_jobs = connection.execute(
                "SELECT COUNT(*) FROM training_jobs WHERE status IN ('queued', 'running')"
            ).fetchone()[0]
            latest_jobs = connection.execute(
                "SELECT * FROM training_jobs ORDER BY created_at DESC, id DESC LIMIT 5"
            ).fetchall()
        jobs = []
        for row in latest_jobs:
            job = dict(row)
            job["document_ids"] = json.loads(job["document_ids"])
            jobs.append(job)
        return {
            "documents": documents,
            "indexed_documents": indexed_documents,
            "open_feedback": open_feedback,
            "active_jobs": active_jobs,
            "latest_jobs": jobs,
        }

    async def overview(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._overview_sync)

    def _list_audit_events_sync(
        self,
        *,
        search: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        where = ""
        parameters: list[Any] = []
        if search:
            where = (
                "WHERE action LIKE ? OR entity_type LIKE ? "
                "OR COALESCE(entity_id, '') LIKE ? OR details LIKE ?"
            )
            pattern = f"%{search}%"
            parameters = [pattern, pattern, pattern, pattern]
        with self._connect() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM admin_audit_log {where}",
                parameters,
            ).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT id, action, entity_type, entity_id, details, created_at
                FROM admin_audit_log
                {where}
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                [*parameters, limit, offset],
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                item["details"] = json.loads(item["details"])
            except (TypeError, json.JSONDecodeError):
                item["details"] = {}
            items.append(item)
        return {"items": items, "total": total}

    async def list_audit_events(self, **filters: Any) -> dict[str, Any]:
        return await asyncio.to_thread(self._list_audit_events_sync, **filters)
