import asyncio
import json
from datetime import datetime

import pytest

import app.whatsapp as whatsapp_module
import app.webhook_queue as webhook_queue_module
import app.config as config_module
import app.training as training_module
from app.admin_store import AdminStore, VersionConflictError
from app.config import (
    get_settings,
    public_runtime_settings,
    runtime_configuration_version,
    update_runtime_configuration,
    update_runtime_settings,
)
from app.vector_store import VectorStore
from app.whatsapp import (
    WhatsAppBot,
    WhatsAppInboundBusyError,
    WhatsAppIncomingMessage,
    feedback_session_key,
    split_feedback_marker,
    verify_meta_signature,
)


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"northstar-feedback-png"
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"northstar-feedback-jpeg"


@pytest.fixture(autouse=True)
def isolated_admin_paths(tmp_path, monkeypatch):
    """Keep settings-backed writes out of the repository for every test."""
    monkeypatch.setenv("APP_ENVIRONMENT", "test")
    monkeypatch.setenv("ADMIN_DATABASE_FILE", str(tmp_path / "admin.sqlite3"))
    monkeypatch.setenv("FEEDBACK_MEDIA_DIRECTORY", str(tmp_path / "feedback-media"))
    monkeypatch.setenv("RUNTIME_CONFIG_FILE", str(tmp_path / "runtime-config.json"))
    monkeypatch.setenv("MENTOR_SYSTEM_PROMPT_FILE", str(tmp_path / "mentor-system-prompt.txt"))
    monkeypatch.setenv(
        "WHATSAPP_FEEDBACK_PREFILL",
        "FEEDBACK\nPlease describe the change or error. You can also attach a screenshot.",
    )
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def run(coroutine):
    return asyncio.run(coroutine)


def create_document(store: AdminStore, *, title: str = "Variance notes", course: str = "CMA"):
    return run(
        store.create_document(
            title=title,
            filename=f"{title.lower().replace(' ', '-')}.md",
            course=course,
            doc_type="notes",
            content="Original lesson content for the mentor.",
        )
    )


def test_admin_store_document_crud_and_version_conflicts():
    store = AdminStore()
    created = create_document(store)

    assert created["status"] == "draft"
    assert created["version"] == 1
    assert created["content"] == "Original lesson content for the mentor."

    listing = run(store.list_documents(search="variance", course="CMA", status="draft"))
    assert listing["total"] == 1
    assert listing["items"][0]["id"] == created["id"]
    assert listing["items"][0]["character_count"] == len(created["content"])

    updated = run(
        store.update_document(
            created["id"],
            title="Updated variance notes",
            course="CPA",
            doc_type="lesson",
            content="Revised and editable lesson content.",
            expected_version=1,
        )
    )
    assert updated is not None
    assert updated["version"] == 2
    assert updated["course"] == "CPA"
    assert updated["status"] == "draft"

    with pytest.raises(VersionConflictError, match="changed after it was opened"):
        run(
            store.update_document(
                created["id"],
                title="Stale edit",
                course="CPA",
                doc_type="lesson",
                content="This stale write must not win.",
                expected_version=1,
            )
        )

    persisted = run(store.get_document(created["id"]))
    assert persisted is not None
    assert persisted["title"] == "Updated variance notes"
    assert persisted["content"] == "Revised and editable lesson content."
    assert run(store.delete_document(created["id"])) is True
    assert run(store.delete_document(created["id"])) is False
    assert run(store.get_document(created["id"])) is None


def test_document_upload_batch_rolls_back_completely_on_insert_failure(monkeypatch):
    store = AdminStore()
    original_audit = store._audit_sync
    calls = 0

    def fail_second_audit(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated audit failure")
        return original_audit(*args, **kwargs)

    monkeypatch.setattr(store, "_audit_sync", fail_second_audit)
    documents = [
        {
            "title": "First upload",
            "filename": "first.md",
            "course": "CMA",
            "doc_type": "lesson",
            "content": "First source text.",
        },
        {
            "title": "Second upload",
            "filename": "second.md",
            "course": "CMA",
            "doc_type": "lesson",
            "content": "Second source text.",
        },
    ]

    with pytest.raises(RuntimeError, match="simulated audit failure"):
        run(store.create_documents(documents))

    assert run(store.list_documents())["total"] == 0
    assert run(store.list_audit_events())["total"] == 0


def test_admin_store_training_job_state_transitions_and_conflicts():
    store = AdminStore()
    first = create_document(store, title="First source")
    second = create_document(store, title="Second source", course="CPA")

    with pytest.raises(KeyError):
        run(store.create_training_job(["missing-document"]))

    job = run(store.create_training_job([first["id"], second["id"]]))
    assert job["status"] == "queued"
    assert job["document_ids"] == [first["id"], second["id"]]
    assert job["total_documents"] == 2
    assert run(store.get_document(first["id"]))["status"] == "queued"

    with pytest.raises(VersionConflictError, match="already active"):
        run(store.create_training_job([first["id"]]))

    claimed = run(store.claim_training_job(job["id"]))
    assert claimed is not None
    assert claimed["status"] == "running"
    assert claimed["started_at"] is not None
    assert run(store.claim_training_job(job["id"])) is None

    run(store.set_document_status(first["id"], "indexed", chunk_count=7))
    run(store.set_document_status(second["id"], "failed", error_message="embedding failed"))
    run(store.update_training_progress(job["id"], completed_delta=1, chunk_delta=7))
    run(store.update_training_progress(job["id"], failed_delta=1))
    run(store.finish_training_job(job["id"]))

    jobs = run(store.list_training_jobs())
    assert jobs["total"] == 1
    completed = jobs["items"][0]
    assert completed["status"] == "partial"
    assert completed["completed_documents"] == 1
    assert completed["failed_documents"] == 1
    assert completed["total_chunks"] == 7
    assert completed["completed_at"] is not None


def test_published_revision_allowlist_survives_an_interrupted_job_requeue():
    store = AdminStore()
    document = create_document(store)
    job = run(store.create_training_job([document["id"]]))
    assert run(store.claim_training_job(job["id"])) is not None
    run(store.set_document_status(document["id"], "indexing"))
    run(
        store.publish_document_revision(
            document["id"],
            expected_version=1,
            chunk_count=4,
        )
    )

    assert run(store.list_published_source_revisions()) == [f"{document['id']}:1"]
    assert run(store.requeue_training_job(job["id"])) is True
    recovered = run(store.get_document(document["id"]))
    assert recovered["status"] == "queued"
    assert recovered["published_version"] == 1
    assert run(store.requeue_training_job(job["id"])) is False


def test_stale_job_recovery_never_overwrites_a_durable_delete_intent():
    store = AdminStore()
    document = create_document(store)
    job = run(store.create_training_job([document["id"]]))
    run(store.claim_training_job(job["id"]))
    with store._connect() as connection:
        connection.execute(
            "UPDATE knowledge_documents SET status = 'deleting' WHERE id = ?",
            (document["id"],),
        )
        connection.execute(
            "UPDATE training_jobs SET heartbeat_at = '2000-01-01T00:00:00+00:00' WHERE id = ?",
            (job["id"],),
        )

    assert job["id"] in run(store.recover_training_jobs())
    assert run(store.get_document(document["id"]))["status"] == "deleting"


def test_recovered_training_job_fences_the_previous_worker_lease():
    store = AdminStore()
    document = create_document(store)
    job = run(store.create_training_job([document["id"]]))
    first_claim = run(store.claim_training_job(job["id"]))
    first_token = first_claim["lease_token"]
    with store._connect() as connection:
        connection.execute(
            "UPDATE training_jobs SET heartbeat_at = '2000-01-01T00:00:00+00:00' WHERE id = ?",
            (job["id"],),
        )

    assert job["id"] in run(store.recover_training_jobs())
    second_claim = run(store.claim_training_job(job["id"]))
    second_token = second_claim["lease_token"]
    assert second_token != first_token
    assert run(store.touch_training_job(job["id"], first_token)) is False
    assert run(
        store.update_training_progress(
            job["id"],
            completed_delta=1,
            lease_token=first_token,
        )
    ) is False
    assert run(store.finish_training_job(job["id"], lease_token=first_token)) is False
    assert run(store.requeue_training_job(job["id"], first_token)) is False
    assert run(store.touch_training_job(job["id"], second_token)) is True


def test_training_worker_indexes_and_publishes_a_document(monkeypatch):
    store = AdminStore()
    document = create_document(store, title="Worker success")
    job = run(store.create_training_job([document["id"]]))
    calls: dict[str, object] = {}

    class FakeEmbeddingService:
        async def embed_many(self, texts):
            calls["embedded"] = list(texts)
            return [[0.1] * get_settings().embedding_dimensions for _ in texts]

        async def aclose(self):
            calls["embedder_closed"] = True

    class FakeClient:
        async def close(self):
            calls["vector_closed"] = True

    class FakeVectorStore:
        def __init__(self):
            self.client = FakeClient()

        async def replace_source_chunks(self, **values):
            calls["indexed"] = values
            return len(values["texts"])

        async def prune_source_revisions(self, source_id, revision):
            calls["pruned"] = (source_id, revision)

    monkeypatch.setattr(training_module, "EmbeddingService", FakeEmbeddingService)
    monkeypatch.setattr(training_module, "VectorStore", FakeVectorStore)

    run(training_module.run_training_job(job["id"]))

    completed = run(store.get_training_job(job["id"]))
    published = run(store.get_document(document["id"]))
    assert completed["status"] == "completed"
    assert completed["completed_documents"] == 1
    assert completed["failed_documents"] == 0
    assert completed["total_chunks"] > 0
    assert published["status"] == "indexed"
    assert published["published_version"] == published["version"] == 1
    assert calls["pruned"] == (document["id"], 1)
    assert calls["embedder_closed"] is True
    assert calls["vector_closed"] is True


def test_training_worker_records_embedding_failure_without_wedging_document(monkeypatch):
    store = AdminStore()
    document = create_document(store, title="Worker failure")
    job = run(store.create_training_job([document["id"]]))

    class FailingEmbeddingService:
        async def embed_many(self, texts):
            raise RuntimeError("embedding service unavailable")

        async def aclose(self):
            return None

    monkeypatch.setattr(training_module, "EmbeddingService", FailingEmbeddingService)

    run(training_module.run_training_job(job["id"]))

    completed = run(store.get_training_job(job["id"]))
    failed = run(store.get_document(document["id"]))
    assert completed["status"] == "failed"
    assert completed["failed_documents"] == 1
    assert failed["status"] == "failed"
    assert "embedding service unavailable" in failed["error_message"]


def test_vector_search_filters_to_catalog_published_revisions():
    store = AdminStore()
    document = create_document(store)
    job = run(store.create_training_job([document["id"]]))
    run(store.claim_training_job(job["id"]))
    run(store.set_document_status(document["id"], "indexing"))
    run(store.publish_document_revision(document["id"], expected_version=1, chunk_count=1))

    class FakeVectorClient:
        query_filter = None

        async def search(self, **values):
            self.query_filter = values["query_filter"]
            return []

    vector_store = VectorStore()
    vector_store.client = FakeVectorClient()

    async def no_collection_check():
        return None

    vector_store.ensure_collection = no_collection_check
    assert run(vector_store.search(query_vector=[0.0], course="CMA")) == []
    condition = next(
        item for item in vector_store.client.query_filter.must if item.key == "source_revision"
    )
    assert condition.match.any == [f"{document['id']}:1"]


@pytest.mark.parametrize(
    ("mime_type", "image_bytes", "suffix"),
    [
        ("image/jpeg", JPEG_BYTES, ".jpg"),
        ("image/png", PNG_BYTES, ".png"),
    ],
)
def test_feedback_image_persistence_dedupe_status_and_raw_immutability(
    mime_type, image_bytes, suffix
):
    store = AdminStore()
    original = run(
        store.create_feedback(
            whatsapp_message_id="wamid.feedback-1",
            sender="919999999999",
            profile_name="Student",
            message="The answer screen shows a wrong formula error.",
            image_bytes=image_bytes,
            mime_type=mime_type,
        )
    )

    assert original["category"] == "error"
    assert original["status"] == "open"
    assert original["attachment_filename"].endswith(suffix)
    assert original["attachment_size"] == len(image_bytes)
    attachment = store.attachment_path(original)
    assert attachment is not None
    assert attachment.parent == store.media_directory.resolve()
    assert attachment.read_bytes() == image_bytes

    duplicate = run(
        store.create_feedback(
            whatsapp_message_id="wamid.feedback-1",
            sender="910000000000",
            profile_name="Different sender",
            message="A duplicate delivery must not overwrite the raw message.",
            image_bytes=image_bytes + b"duplicate",
            mime_type=mime_type,
        )
    )
    assert duplicate["id"] == original["id"]
    assert duplicate["sender"] == "919999999999"
    assert duplicate["message"] == "The answer screen shows a wrong formula error."
    assert [path.name for path in store.media_directory.iterdir()] == [
        original["attachment_filename"]
    ]

    updated = run(
        store.update_feedback(
            original["id"],
            status="resolved",
            category="change",
            admin_notes="Corrected in the current knowledge revision.",
        )
    )
    assert updated is not None
    assert updated["status"] == "resolved"
    assert updated["category"] == "change"
    assert updated["has_attachment"] is True
    assert updated["message"] == original["message"]
    assert updated["sender"] == original["sender"]
    assert updated["whatsapp_message_id"] == original["whatsapp_message_id"]

    persisted = run(store.get_feedback(original["id"]))
    assert persisted is not None
    assert persisted["message"] == original["message"]
    assert persisted["attachment_filename"] == original["attachment_filename"]
    resolved = run(store.list_feedback(status="resolved", category="change"))
    assert resolved["total"] == 1
    assert resolved["items"][0]["has_attachment"] is True


def test_feedback_rejects_spoofed_images_and_blocks_attachment_path_traversal(tmp_path):
    store = AdminStore()

    with pytest.raises(ValueError, match="valid JPEG or PNG"):
        run(
            store.create_feedback(
                whatsapp_message_id="wamid.invalid-image",
                sender="919999999999",
                profile_name=None,
                message="This is not really a screenshot.",
                image_bytes=b"not-an-image",
                mime_type="image/png",
            )
        )

    assert run(store.list_feedback())["total"] == 0
    assert list(store.media_directory.iterdir()) == []

    outside = tmp_path / "outside.png"
    outside.write_bytes(PNG_BYTES)
    assert store.attachment_path({"attachment_filename": "../outside.png"}) is None
    assert store.attachment_path({"attachment_filename": str(outside.resolve())}) is None


def test_feedback_sessions_are_durable_and_clearable():
    store = AdminStore()
    sender = "919999999999"
    run(store.set_feedback_session(sender, "awaiting_submission", 300))
    assert run(store.get_feedback_session(sender)) == "awaiting_submission"
    run(store.clear_feedback_session(sender))
    assert run(store.get_feedback_session(sender)) is None


def test_whatsapp_webhook_queue_is_durable_deduplicated_and_retryable():
    store = AdminStore()
    payload = {"entry": [{"id": "entry-1", "changes": []}]}
    first = run(store.enqueue_whatsapp_webhook(payload))
    duplicate = run(store.enqueue_whatsapp_webhook(payload))
    assert duplicate["id"] == first["id"]

    claimed = run(store.claim_whatsapp_webhook(first["id"]))
    assert claimed is not None
    assert claimed["attempts"] == 1
    assert run(
        store.finish_whatsapp_webhook(
            first["id"],
            claimed["lease_token"],
            "temporary failure",
        )
    ) is True
    with store._connect() as connection:
        connection.execute(
            "UPDATE whatsapp_webhook_events SET available_at = '2000-01-01T00:00:00+00:00' WHERE id = ?",
            (first["id"],),
        )
    assert first["id"] in run(store.due_whatsapp_webhooks())

    retried = run(store.claim_whatsapp_webhook(first["id"]))
    assert retried is not None
    assert retried["attempts"] == 2
    assert retried["lease_token"] != claimed["lease_token"]
    assert run(store.finish_whatsapp_webhook(first["id"], retried["lease_token"])) is True
    assert first["id"] not in run(store.due_whatsapp_webhooks())


def test_whatsapp_queue_recent_inbound_marker_ignores_status_only_callbacks():
    store = AdminStore()
    status_payload = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {"statuses": [{"id": "wamid.status"}]}}]}],
    }
    run(store.enqueue_whatsapp_webhook(status_payload))
    status_summary = run(store.whatsapp_queue_summary())

    assert status_summary["latest_event"] is not None
    assert status_summary["latest_inbound_message_at"] is None

    message_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.inbound",
                                    "from": "919999999999",
                                    "type": "text",
                                    "text": {"body": "Hi"},
                                }
                            ]
                        }
                    }
                ]
            }
        ],
    }
    message = run(store.enqueue_whatsapp_webhook(message_payload))
    message_summary = run(store.whatsapp_queue_summary())

    assert message["inbound_message_count"] == 1
    assert message_summary["latest_inbound_message_at"] == message["created_at"]


def test_whatsapp_webhook_queue_dead_letters_after_the_configured_attempts(monkeypatch):
    monkeypatch.setenv("WHATSAPP_WEBHOOK_MAX_ATTEMPTS", "1")
    get_settings.cache_clear()
    store = AdminStore()
    event = run(store.enqueue_whatsapp_webhook({"entry": [{"id": "permanent-failure"}]}))
    claimed = run(store.claim_whatsapp_webhook(event["id"]))

    assert run(
        store.finish_whatsapp_webhook(
            event["id"],
            claimed["lease_token"],
            "permanent payload failure",
        )
    ) is True
    with store._connect() as connection:
        persisted = connection.execute(
            "SELECT status, attempts, last_error FROM whatsapp_webhook_events WHERE id = ?",
            (event["id"],),
        ).fetchone()
    assert persisted["status"] == "dead_letter"
    assert persisted["attempts"] == 1
    assert persisted["last_error"] == "permanent payload failure"
    assert event["id"] not in run(store.due_whatsapp_webhooks())

    crashed = run(store.enqueue_whatsapp_webhook({"entry": [{"id": "crashed-worker"}]}))
    assert run(store.claim_whatsapp_webhook(crashed["id"])) is not None
    with store._connect() as connection:
        connection.execute(
            "UPDATE whatsapp_webhook_events SET updated_at = '2000-01-01T00:00:00+00:00' WHERE id = ?",
            (crashed["id"],),
        )
    assert crashed["id"] not in run(store.due_whatsapp_webhooks())
    with store._connect() as connection:
        crashed_status = connection.execute(
            "SELECT status FROM whatsapp_webhook_events WHERE id = ?",
            (crashed["id"],),
        ).fetchone()["status"]
    assert crashed_status == "dead_letter"


def test_whatsapp_webhook_heartbeat_renews_and_fences_lost_ownership(monkeypatch):
    class FakeStore:
        calls = 0

        async def touch_whatsapp_webhook(self, event_id, lease_token):
            self.calls += 1
            assert event_id == "event-1"
            assert lease_token == "lease-1"
            return self.calls == 1

    class FakeOwner:
        cancelled = False

        def cancel(self):
            self.cancelled = True

    async def elapse_immediately(awaitable, *, timeout):
        awaitable.close()
        raise TimeoutError

    monkeypatch.setattr(webhook_queue_module.asyncio, "wait_for", elapse_immediately)
    store = FakeStore()
    owner = FakeOwner()
    run(
        webhook_queue_module._heartbeat_whatsapp_webhook(
            store,
            "event-1",
            "lease-1",
            owner,
            asyncio.Event(),
        )
    )
    assert store.calls == 2
    assert owner.cancelled is True


def test_whatsapp_webhook_workers_serialize_feedback_session_order(monkeypatch):
    store = AdminStore()
    active = 0
    maximum_active = 0
    order = []

    async def process(payload):
        nonlocal active, maximum_active
        event_name = payload["entry"][0]["id"]
        active += 1
        maximum_active = max(maximum_active, active)
        order.append(event_name)
        await asyncio.sleep(0.02)
        active -= 1

    monkeypatch.setattr(webhook_queue_module, "process_whatsapp_webhook", process)

    async def scenario():
        first = await store.enqueue_whatsapp_webhook({"entry": [{"id": "feedback-marker"}]})
        second = await store.enqueue_whatsapp_webhook({"entry": [{"id": "feedback-description"}]})
        first_task = asyncio.create_task(
            webhook_queue_module.run_whatsapp_webhook_event(first["id"])
        )
        await asyncio.sleep(0)
        second_task = asyncio.create_task(
            webhook_queue_module.run_whatsapp_webhook_event(second["id"])
        )
        await asyncio.gather(first_task, second_task)

    run(scenario())
    assert maximum_active == 1
    assert order == ["feedback-marker", "feedback-description"]


def test_busy_inbound_marker_defers_the_durable_webhook_until_its_ttl(monkeypatch):
    store = AdminStore()
    event = run(store.enqueue_whatsapp_webhook({"entry": [{"id": "busy-inbound"}]}))

    async def busy(_payload):
        raise WhatsAppInboundBusyError("wamid.busy", 300)

    monkeypatch.setattr(webhook_queue_module, "process_whatsapp_webhook", busy)
    run(webhook_queue_module.run_whatsapp_webhook_event(event["id"]))

    with store._connect() as connection:
        row = connection.execute(
            "SELECT status, available_at, updated_at FROM whatsapp_webhook_events WHERE id = ?",
            (event["id"],),
        ).fetchone()
    assert row["status"] == "failed"
    assert (
        datetime.fromisoformat(row["available_at"])
        - datetime.fromisoformat(row["updated_at"])
    ).total_seconds() == 300


def test_feedback_retention_purges_expired_record_and_attachment():
    store = AdminStore()
    feedback = run(
        store.create_feedback(
            whatsapp_message_id="wamid.expired-feedback",
            sender="919999999999",
            profile_name=None,
            message="An old issue",
            image_bytes=PNG_BYTES,
            mime_type="image/png",
        )
    )
    attachment = store.attachment_path(feedback)
    assert attachment is not None and attachment.exists()
    with store._connect() as connection:
        connection.execute(
            "UPDATE feedback SET created_at = '2000-01-01T00:00:00+00:00' WHERE id = ?",
            (feedback["id"],),
        )

    assert run(store.purge_expired_feedback()) == 1
    assert run(store.get_feedback(feedback["id"])) is None
    assert not attachment.exists()


def test_runtime_settings_persist_only_allowlisted_non_secret_values(tmp_path):
    updated = update_runtime_settings(
        {
            "top_k": 9,
            "strict_grounding": False,
            "whatsapp_feedback_number": "919876543210",
        }
    )
    assert updated.top_k == 9
    assert updated.strict_grounding is False
    assert updated.whatsapp_feedback_number == "919876543210"

    runtime_path = tmp_path / "runtime-config.json"
    payload = json.loads(runtime_path.read_text(encoding="utf-8"))
    assert payload["top_k"] == 9
    assert payload["whatsapp_feedback_number"] == "919876543210"
    assert "admin_token" not in payload
    assert "nvidia_api_key" not in payload
    assert "whatsapp_access_token" not in payload

    public = public_runtime_settings(updated)
    assert set(public) == {key for key in payload if not key.startswith("_")}
    assert "admin_token" not in public

    before = runtime_path.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="not dashboard-editable"):
        update_runtime_settings({"admin_token": "must-not-be-persisted"})
    assert runtime_path.read_text(encoding="utf-8") == before

    get_settings.cache_clear()
    reloaded = get_settings()
    assert reloaded.top_k == 9
    assert reloaded.whatsapp_feedback_number == "919876543210"


def test_atomic_configuration_write_preserves_previous_version_on_replace_failure(
    tmp_path,
    monkeypatch,
):
    prompt = "Use clear, course-specific explanations. " * 5
    current_version = runtime_configuration_version()
    _, _, saved_version = update_runtime_configuration(
        {"top_k": 8},
        system_prompt=prompt,
        expected_version=current_version,
    )
    runtime_path = tmp_path / "runtime-config.json"
    original = runtime_path.read_bytes()

    monkeypatch.setattr(
        config_module.os,
        "replace",
        lambda *_args: (_ for _ in ()).throw(PermissionError("locked")),
    )
    with pytest.raises(PermissionError, match="locked"):
        update_runtime_configuration(
            {"top_k": 4},
            system_prompt=prompt + " Keep examples practical.",
            expected_version=saved_version,
        )

    assert runtime_path.read_bytes() == original
    assert list(tmp_path.glob(".runtime-config.json.*.tmp")) == []


class FakeFeedbackCache:
    def __init__(self):
        self.values = {}

    async def get_text(self, key):
        return self.values.get(key)

    async def set_if_absent(self, key, ttl_seconds):
        if key in self.values:
            return False
        self.values[key] = "processing"
        return True

    async def set_text(self, key, value, ttl_seconds):
        self.values[key] = value

    async def delete(self, key):
        self.values.pop(key, None)


class FakeFeedbackClient:
    def __init__(self):
        self.texts = []
        self.downloads = []

    async def send_text(self, to, body):
        self.texts.append((to, body))
        return {}

    async def download_media(self, media_id):
        self.downloads.append(media_id)
        return PNG_BYTES, "image/png"


class FakeFeedbackStore:
    def __init__(self):
        self.calls = []
        self.sessions = {}

    async def create_feedback(self, **values):
        self.calls.append(values)
        return {"id": "ABCDEF12-3456-7890-ABCD-EF1234567890"}

    async def get_feedback_session(self, sender):
        return self.sessions.get(sender)

    async def set_feedback_session(self, sender, state, ttl_seconds):
        self.sessions[sender] = state

    async def clear_feedback_session(self, sender):
        self.sessions.pop(sender, None)


def feedback_bot():
    bot = WhatsAppBot()
    cache = FakeFeedbackCache()
    client = FakeFeedbackClient()
    store = FakeFeedbackStore()
    bot.cache = cache
    bot.client = client
    bot.feedback_store_factory = lambda: store
    return bot, cache, client, store


def test_feedback_marker_parser_requires_a_deliberate_prefix():
    assert split_feedback_marker("[FEEDBACK]: The save button fails") == (
        True,
        "The save button fails",
    )
    assert split_feedback_marker("FEEDBACK\nPlease change the answer") == (
        True,
        "Please change the answer",
    )
    assert split_feedback_marker("Please explain feedback loops") == (False, "")
    assert split_feedback_marker("feedbacking is not a marker") == (False, "")
    assert split_feedback_marker("Feedback control systems are part of this lesson") == (False, "")


def test_whatsapp_feedback_prefill_opens_session_and_followup_image_is_saved():
    bot, cache, client, store = feedback_bot()
    sender = "919999999999"

    async def scenario():
        await bot._handle_message(
            WhatsAppIncomingMessage(
                message_id="wamid.feedback-start",
                sender=sender,
                text=bot.settings.whatsapp_feedback_prefill,
                message_type="text",
                profile_name="Student",
            )
        )
        assert store.sessions[sender] == "awaiting_submission"
        assert feedback_session_key(sender) not in cache.values
        assert store.calls == []

        await bot._handle_message(
            WhatsAppIncomingMessage(
                message_id="wamid.feedback-image",
                sender=sender,
                text="The dashboard save button shows this error.",
                message_type="image",
                profile_name="Student",
                media_id="media-feedback-1",
                media_mime_type="image/png",
            )
        )
        assert sender not in store.sessions

    run(scenario())

    assert client.downloads == ["media-feedback-1"]
    assert len(store.calls) == 1
    saved = store.calls[0]
    assert saved["whatsapp_message_id"] == "wamid.feedback-image"
    assert saved["sender"] == sender
    assert saved["message"] == "The dashboard save button shows this error."
    assert saved["image_bytes"] == PNG_BYTES
    assert saved["mime_type"] == "image/png"
    assert "Reference: *ABCDEF12*" in client.texts[-1][1]


def test_whatsapp_marked_text_feedback_bypasses_enrollment_and_session_can_cancel():
    bot, cache, client, store = feedback_bot()
    sender = "919999999999"

    async def scenario():
        await bot._handle_message(
            WhatsAppIncomingMessage(
                message_id="wamid.feedback-text",
                sender=sender,
                text="[FEEDBACK] The revision answer needs another example.",
                message_type="text",
            )
        )
        assert store.calls[0]["message"] == "The revision answer needs another example."
        assert store.calls[0]["image_bytes"] is None

        await bot._handle_message(
            WhatsAppIncomingMessage(
                message_id="wamid.feedback-start-2",
                sender=sender,
                text="FEEDBACK",
                message_type="text",
            )
        )
        assert store.sessions[sender] == "awaiting_submission"

        await bot._handle_message(
            WhatsAppIncomingMessage(
                message_id="wamid.feedback-cancel",
                sender=sender,
                text="cancel",
                message_type="text",
            )
        )
        assert sender not in store.sessions

    run(scenario())

    assert len(store.calls) == 1
    assert any("Feedback cancelled" in body for _, body in client.texts)


def test_hi_clears_a_pending_feedback_session_and_continues_to_the_menu():
    bot, _, client, store = feedback_bot()
    sender = "919999999999"
    store.sessions[sender] = "awaiting_submission"

    handled = run(
        bot._handle_feedback_message(
            WhatsAppIncomingMessage(
                message_id="wamid.feedback-hi-reset",
                sender=sender,
                text="Hi 👋",
                message_type="text",
            ),
            is_image=False,
            incoming="Hi 👋",
        )
    )

    assert handled is False
    assert sender not in store.sessions
    assert store.calls == []
    assert client.texts == []


def test_feedback_cancel_session_survives_a_failed_acknowledgement():
    bot, cache, client, store = feedback_bot()
    sender = "919999999999"
    original_send = client.send_text
    fail_cancel_ack = True

    async def flaky_send(to, body):
        nonlocal fail_cancel_ack
        if fail_cancel_ack and body.startswith("Feedback cancelled"):
            fail_cancel_ack = False
            raise RuntimeError("temporary cancellation acknowledgement failure")
        return await original_send(to, body)

    client.send_text = flaky_send

    async def scenario():
        await bot._handle_message(
            WhatsAppIncomingMessage(
                message_id="wamid.feedback-cancel-start",
                sender=sender,
                text="FEEDBACK",
                message_type="text",
            )
        )
        cancel = WhatsAppIncomingMessage(
            message_id="wamid.feedback-cancel-retry",
            sender=sender,
            text="cancel",
            message_type="text",
        )
        with pytest.raises(RuntimeError, match="temporary cancellation acknowledgement failure"):
            await bot._handle_message(cancel)
        assert store.sessions[sender] == "awaiting_submission"
        assert feedback_session_key(sender) not in cache.values

        await bot._handle_message(cancel)
        assert sender not in store.sessions

    run(scenario())


def test_rejected_feedback_image_keeps_durable_session_for_followup_text():
    bot, _, client, store = feedback_bot()
    original_create = store.create_feedback
    attempts = 0

    async def reject_feedback(**values):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ValueError("Feedback screenshot storage limit reached")
        return await original_create(**values)

    store.create_feedback = reject_feedback
    sender = "919999999999"

    async def scenario():
        assert await bot._handle_feedback_message(
            WhatsAppIncomingMessage(
                message_id="wamid.feedback-image-limit",
                sender=sender,
                text="[FEEDBACK] Screenshot of the wrong answer",
                message_type="image",
                media_id="media-limit",
            ),
            is_image=True,
            incoming="[FEEDBACK] Screenshot of the wrong answer",
        ) is True
        assert store.sessions[sender] == "awaiting_submission"

        await bot._handle_feedback_message(
            WhatsAppIncomingMessage(
                message_id="wamid.feedback-text-after-image",
                sender=sender,
                text="The answer needs a correction.",
                message_type="text",
            ),
            is_image=False,
            incoming="The answer needs a correction.",
        )
        assert sender not in store.sessions

    run(scenario())
    assert attempts == 2
    assert len(store.calls) == 1
    assert store.calls[0]["message"] == "The answer needs a correction."
    assert "or type your feedback" in client.texts[0][1]
    assert client.texts[-1][1].startswith("Thank you")


def test_stale_redis_feedback_session_cannot_resurrect_a_closed_sqlite_session():
    bot, cache, _, store = feedback_bot()
    sender = "919999999999"
    cache.values[feedback_session_key(sender)] = "awaiting_submission"
    assert store.sessions == {}

    handled = run(
        bot._handle_feedback_message(
            WhatsAppIncomingMessage(
                message_id="wamid.normal-question",
                sender=sender,
                text="Explain variance analysis",
                message_type="text",
            ),
            is_image=False,
            incoming="Explain variance analysis",
        )
    )
    assert handled is False
    assert store.calls == []


def test_feedback_session_survives_failed_acknowledgement_for_meta_retry():
    bot, cache, client, store = feedback_bot()
    sender = "919999999999"
    original_send = client.send_text
    fail_ack = True

    async def flaky_send(to, body):
        nonlocal fail_ack
        if fail_ack and body.startswith("Thank you"):
            fail_ack = False
            raise RuntimeError("temporary WhatsApp send failure")
        return await original_send(to, body)

    client.send_text = flaky_send

    async def scenario():
        await bot._handle_message(
            WhatsAppIncomingMessage(
                message_id="wamid.feedback-start-retry",
                sender=sender,
                text="FEEDBACK",
                message_type="text",
            )
        )
        followup = WhatsAppIncomingMessage(
            message_id="wamid.feedback-followup-retry",
            sender=sender,
            text="The lesson link is broken.",
            message_type="text",
        )
        with pytest.raises(RuntimeError, match="temporary WhatsApp send failure"):
            await bot._handle_message(followup)
        assert store.sessions[sender] == "awaiting_submission"
        assert feedback_session_key(sender) not in cache.values

        await bot._handle_message(followup)
        assert sender not in store.sessions

    run(scenario())


def test_whatsapp_dedupe_is_committed_only_after_success(monkeypatch):
    bot, cache, _, _ = feedback_bot()
    message = WhatsAppIncomingMessage(
        message_id="wamid.retryable",
        sender="919999999999",
        text="hello",
        message_type="text",
    )
    attempts = 0

    async def flaky_handler(_message):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary provider failure")

    monkeypatch.setattr(whatsapp_module, "extract_status_events", lambda payload: [])
    monkeypatch.setattr(whatsapp_module, "extract_incoming_messages", lambda payload: [message])
    bot._handle_message = flaky_handler

    with pytest.raises(RuntimeError, match="wamid.retryable"):
        run(bot.handle_payload({}))
    assert attempts == 1
    assert f"whatsapp:inbound:done:{message.message_id}" not in cache.values
    assert f"whatsapp:inbound:processing:{message.message_id}" not in cache.values

    run(bot.handle_payload({}))
    assert attempts == 2
    assert cache.values[f"whatsapp:inbound:done:{message.message_id}"] == "1"


def test_whatsapp_cancellation_releases_the_inflight_dedupe_marker(monkeypatch):
    bot, cache, _, _ = feedback_bot()
    message = WhatsAppIncomingMessage(
        message_id="wamid.cancelled-worker",
        sender="919999999999",
        text="hello",
        message_type="text",
    )

    async def cancelled_handler(_message):
        raise asyncio.CancelledError

    monkeypatch.setattr(whatsapp_module, "extract_status_events", lambda payload: [])
    monkeypatch.setattr(whatsapp_module, "extract_incoming_messages", lambda payload: [message])
    bot._handle_message = cancelled_handler

    with pytest.raises(asyncio.CancelledError):
        run(bot.handle_payload({}))
    assert f"whatsapp:inbound:processing:{message.message_id}" not in cache.values
    assert f"whatsapp:inbound:done:{message.message_id}" not in cache.values


def test_surviving_cancel_marker_never_false_completes_the_retry(monkeypatch):
    bot, cache, _, _ = feedback_bot()
    message = WhatsAppIncomingMessage(
        message_id="wamid.sticky-cancel",
        sender="919999999999",
        text="hello",
        message_type="text",
    )
    attempts = 0

    async def sticky_delete(_key):
        return None

    async def cancelled_handler(_message):
        nonlocal attempts
        attempts += 1
        raise asyncio.CancelledError

    cache.delete = sticky_delete
    monkeypatch.setattr(whatsapp_module, "extract_status_events", lambda payload: [])
    monkeypatch.setattr(whatsapp_module, "extract_incoming_messages", lambda payload: [message])
    bot._handle_message = cancelled_handler

    with pytest.raises(asyncio.CancelledError):
        run(bot.handle_payload({}))
    processing_key = f"whatsapp:inbound:processing:{message.message_id}"
    assert processing_key in cache.values

    with pytest.raises(WhatsAppInboundBusyError) as error:
        run(bot.handle_payload({}))
    assert error.value.retry_after_seconds == bot.settings.whatsapp_inbound_processing_ttl_seconds
    assert attempts == 1
    assert f"whatsapp:inbound:done:{message.message_id}" not in cache.values


def test_whatsapp_signature_fails_closed_without_secret(monkeypatch):
    monkeypatch.setenv("APP_ENVIRONMENT", "development")
    monkeypatch.setenv("WHATSAPP_USE_MOCK", "false")
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "")
    monkeypatch.setenv("META_APP_SECRET", "")
    get_settings.cache_clear()

    assert verify_meta_signature(b"{}", None) is False
