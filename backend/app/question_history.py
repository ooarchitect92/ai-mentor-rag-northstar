import asyncio
import hashlib
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


def normalize_question_text(question: str) -> str:
    """Normalize harmless presentation differences without merging different calculations."""
    normalized = " ".join(question.casefold().strip().split())
    return re.sub(r"[?!.,]+$", "", normalized).strip()


def question_key(course: str, question: str) -> str:
    normalized = normalize_question_text(question)
    return hashlib.sha256(f"{course.upper()}::{normalized}".encode("utf-8")).hexdigest()


class QuestionAnswerStore:
    """Append-only, JSON-lines question and answer library stored in a .txt file."""

    _write_lock = asyncio.Lock()

    def __init__(self, file_path: str) -> None:
        self.path = Path(file_path)

    def _find_first_answer_sync(self, *, course: str, key: str) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if (
                        record.get("course") == course.upper()
                        and record.get("question_key") == key
                        and record.get("kind") == "answer"
                        and record.get("stage") == 1
                        and record.get("reusable") is True
                        and record.get("answer")
                    ):
                        return record
        except OSError:
            return None
        return None

    async def find_first_answer(self, *, course: str, question: str) -> dict[str, Any] | None:
        key = question_key(course, question)
        return await asyncio.to_thread(self._find_first_answer_sync, course=course, key=key)

    def _append_sync(self, record: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()

    async def append(
        self,
        *,
        course: str,
        question: str,
        answer: str,
        stage: int,
        kind: str = "answer",
        reusable: bool = False,
        clarification: str | None = None,
    ) -> None:
        record: dict[str, Any] = {
            "created_at": datetime.now(UTC).isoformat(),
            "course": course.upper(),
            "question_key": question_key(course, question),
            "normalized_question": normalize_question_text(question),
            "question": question,
            "stage": stage,
            "kind": kind,
            "reusable": reusable,
            "answer": answer,
        }
        if clarification:
            record["clarification"] = clarification
        async with self._write_lock:
            try:
                await asyncio.to_thread(self._append_sync, record)
            except OSError:
                # Reusable history is an optimization. A read-only or temporarily
                # unavailable history file must never discard a valid mentor answer.
                logger.exception("Could not persist reusable question history path=%s", self.path)
