import asyncio
import logging

from .admin_store import AdminStore
from .chunking import chunk_text
from .config import get_settings
from .embeddings import EmbeddingService
from .vector_store import VectorStore


logger = logging.getLogger("uvicorn.error")
_training_lock = asyncio.Lock()
_training_tasks: dict[str, asyncio.Task[None]] = {}


class TrainingLeaseLostError(RuntimeError):
    pass


def schedule_training_job(job_id: str, *, replace_existing: bool = False) -> asyncio.Task[None]:
    """Schedule one in-process worker per job while SQLite arbitrates across processes."""
    existing = _training_tasks.get(job_id)
    if existing is not None and not existing.done():
        if not replace_existing:
            return existing
        existing.cancel()
    task = asyncio.create_task(run_training_job(job_id), name=f"knowledge-training-{job_id}")
    _training_tasks[job_id] = task

    def remove_completed(completed: asyncio.Task[None]) -> None:
        if _training_tasks.get(job_id) is completed:
            _training_tasks.pop(job_id, None)

    task.add_done_callback(remove_completed)
    return task


async def cancel_training_tasks() -> None:
    tasks = [task for task in _training_tasks.values() if not task.done()]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def reconcile_deleting_documents() -> None:
    """Finish idempotent deletes left between SQLite and Qdrant by a process crash."""
    store = AdminStore()
    documents = await store.list_deleting_documents()
    vector_store: VectorStore | None = None
    try:
        for document in documents:
            try:
                if document.get("published_version") is not None or int(document.get("chunk_count") or 0) > 0:
                    if vector_store is None:
                        vector_store = VectorStore()
                    await vector_store.delete_source(str(document["id"]))
                await store.delete_document(str(document["id"]))
                logger.info("Reconciled interrupted knowledge delete document=%s", document["id"])
            except Exception:
                logger.exception("Could not reconcile knowledge delete document=%s", document["id"])
    finally:
        if vector_store is not None:
            try:
                await vector_store.client.close()
            except Exception:
                logger.exception("Could not close delete-reconciliation vector client")


async def recover_and_schedule_training() -> None:
    store = AdminStore()
    # A durable delete intent wins over replaying an interrupted indexing job.
    await reconcile_deleting_documents()
    recovery = await store.recover_training_jobs_detailed()
    recovered = set(recovery["recovered"])
    for job_id in recovery["queued"]:
        # Only a newly expired lease owns a stale local task. Ordinary queued
        # tasks keep their identity to avoid cancelling a concurrent claim.
        schedule_training_job(job_id, replace_existing=job_id in recovered)
    purged = await store.purge_expired_feedback()
    if purged:
        logger.info("Purged %s expired feedback record(s)", purged)


async def training_supervisor() -> None:
    """Periodically recover expired leases and interrupted deletes."""
    interval = max(5, int(get_settings().training_recovery_interval_seconds))
    while True:
        try:
            await recover_and_schedule_training()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Knowledge training recovery sweep failed")
        await asyncio.sleep(interval)


async def run_training_job(job_id: str) -> None:
    """Build the derived RAG index for a queued group of source documents."""
    store = AdminStore()
    claimed = False
    lease_token = ""
    embedder: EmbeddingService | None = None
    vector_store: VectorStore | None = None
    try:
        async with _training_lock:
            job = await store.claim_training_job(job_id)
            if job is None:
                return
            claimed = True
            lease_token = str(job["lease_token"])

            try:
                for document_id in job["document_ids"]:
                    document = await store.get_document(document_id)
                    if document is None:
                        if not await store.update_training_progress(
                            job_id,
                            failed_delta=1,
                            lease_token=lease_token,
                        ):
                            raise TrainingLeaseLostError(job_id)
                        continue
                    if document["status"] == "deleting":
                        if not await store.update_training_progress(
                            job_id,
                            failed_delta=1,
                            lease_token=lease_token,
                        ):
                            raise TrainingLeaseLostError(job_id)
                        continue
                    if not await store.touch_training_job(job_id, lease_token):
                        raise TrainingLeaseLostError(job_id)
                    if not await store.set_document_status_for_job(
                        document_id,
                        "indexing",
                        job_id=job_id,
                        lease_token=lease_token,
                    ):
                        raise TrainingLeaseLostError(job_id)
                    try:
                        if embedder is None:
                            embedder = EmbeddingService()
                        if vector_store is None:
                            vector_store = VectorStore()
                        chunks = chunk_text(document["content"])
                        if not chunks:
                            raise ValueError("The document has no indexable text")
                        texts = [chunk.text for chunk in chunks]
                        embeddings: list[list[float]] = []
                        for start in range(0, len(texts), 64):
                            embeddings.extend(await embedder.embed_many(texts[start : start + 64]))
                            if not await store.touch_training_job(job_id, lease_token):
                                raise TrainingLeaseLostError(job_id)
                        latest = await store.get_document(document_id)
                        if latest is None or int(latest["version"]) != int(document["version"]):
                            raise ValueError("The document changed while its index was being built")
                        indexed = await vector_store.replace_source_chunks(
                            texts=texts,
                            embeddings=embeddings,
                            title=document["title"],
                            source_id=document_id,
                            course=document["course"],
                            doc_type=document["doc_type"],
                            revision=int(document["version"]),
                        )
                        if not await store.touch_training_job(job_id, lease_token):
                            raise TrainingLeaseLostError(job_id)
                        if not await store.publish_document_revision_for_job(
                            document_id,
                            expected_version=int(document["version"]),
                            chunk_count=indexed,
                            job_id=job_id,
                            lease_token=lease_token,
                        ):
                            raise TrainingLeaseLostError(job_id)
                        try:
                            await vector_store.prune_source_revisions(
                                document_id,
                                int(document["version"]),
                            )
                        except Exception:
                            # Published-version filtering keeps stale points invisible; cleanup is best effort.
                            logger.exception(
                                "Could not prune superseded vectors document=%s job=%s",
                                document_id,
                                job_id,
                            )
                        if not await store.update_training_progress(
                            job_id,
                            completed_delta=1,
                            chunk_delta=indexed,
                            lease_token=lease_token,
                        ):
                            raise TrainingLeaseLostError(job_id)
                    except asyncio.CancelledError:
                        raise
                    except TrainingLeaseLostError:
                        raise
                    except Exception as exc:
                        if not await store.touch_training_job(job_id, lease_token):
                            raise TrainingLeaseLostError(job_id) from exc
                        message = str(exc).strip()[:1000] or type(exc).__name__
                        logger.exception("Knowledge training failed document=%s job=%s", document_id, job_id)
                        if not await store.set_document_status_for_job(
                            document_id,
                            "failed",
                            job_id=job_id,
                            lease_token=lease_token,
                            error_message=message,
                        ):
                            raise TrainingLeaseLostError(job_id)
                        if not await store.update_training_progress(
                            job_id,
                            failed_delta=1,
                            lease_token=lease_token,
                        ):
                            raise TrainingLeaseLostError(job_id)

                if not await store.finish_training_job(job_id, lease_token=lease_token):
                    raise TrainingLeaseLostError(job_id)
            except asyncio.CancelledError:
                raise
            except TrainingLeaseLostError:
                logger.warning("Knowledge training lease lost job=%s; stale worker stopped", job_id)
            except Exception:
                logger.exception("Knowledge training job interrupted job=%s; requeueing", job_id)
                await store.requeue_training_job(job_id, lease_token)
    except asyncio.CancelledError:
        if claimed:
            try:
                await asyncio.shield(store.requeue_training_job(job_id, lease_token))
            except Exception:
                logger.exception("Could not requeue cancelled knowledge job=%s", job_id)
        raise
    finally:
        if embedder is not None:
            try:
                await embedder.aclose()
            except Exception:
                logger.exception("Could not close training embedding client job=%s", job_id)
        if vector_store is not None:
            try:
                await vector_store.client.close()
            except Exception:
                logger.exception("Could not close training vector client job=%s", job_id)
