import asyncio
import logging
from weakref import WeakKeyDictionary

from .admin_store import AdminStore
from .config import get_settings
from .whatsapp import WhatsAppInboundBusyError, process_whatsapp_webhook


logger = logging.getLogger("uvicorn.error")
_webhook_tasks: dict[str, asyncio.Task[None]] = {}
_delivery_locks: WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock] = WeakKeyDictionary()


def _delivery_lock() -> asyncio.Lock:
    """Serialize payloads in each process so feedback sessions preserve message order."""
    loop = asyncio.get_running_loop()
    lock = _delivery_locks.get(loop)
    if lock is None:
        lock = asyncio.Lock()
        _delivery_locks[loop] = lock
    return lock


async def _heartbeat_whatsapp_webhook(
    store: AdminStore,
    event_id: str,
    lease_token: str,
    owner: asyncio.Task[None],
    stop: asyncio.Event,
) -> None:
    """Keep a live delivery leased and fence the worker if ownership is lost."""
    lease_seconds = max(15, int(get_settings().whatsapp_webhook_lease_timeout_seconds))
    interval = max(5, min(60, lease_seconds // 3))
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
            return
        except TimeoutError:
            pass

        try:
            still_owned = await store.touch_whatsapp_webhook(event_id, lease_token)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Could not renew WhatsApp webhook lease event=%s; stopping its worker",
                event_id,
            )
            owner.cancel()
            return
        if not still_owned:
            logger.warning("WhatsApp webhook lease was lost event=%s", event_id)
            owner.cancel()
            return


def schedule_whatsapp_webhook(
    event_id: str,
    *,
    replace_existing: bool = False,
) -> asyncio.Task[None]:
    existing = _webhook_tasks.get(event_id)
    if existing is not None and not existing.done():
        if not replace_existing:
            return existing
        existing.cancel()
    task = asyncio.create_task(
        run_whatsapp_webhook_event(event_id),
        name=f"whatsapp-webhook-{event_id}",
    )
    _webhook_tasks[event_id] = task

    def remove_completed(completed: asyncio.Task[None]) -> None:
        if _webhook_tasks.get(event_id) is completed:
            _webhook_tasks.pop(event_id, None)

    task.add_done_callback(remove_completed)
    return task


async def run_whatsapp_webhook_event(event_id: str) -> None:
    async with _delivery_lock():
        store = AdminStore()
        event = await store.claim_whatsapp_webhook(event_id)
        if event is None:
            return
        lease_token = str(event["lease_token"])
        owner = asyncio.current_task()
        if owner is None:  # pragma: no cover - asyncio always supplies the running task
            raise RuntimeError("WhatsApp webhook worker has no owning task")
        heartbeat_stop = asyncio.Event()
        heartbeat = asyncio.create_task(
            _heartbeat_whatsapp_webhook(store, event_id, lease_token, owner, heartbeat_stop),
            name=f"whatsapp-webhook-heartbeat-{event_id}",
        )
        error_message: str | None = None
        retry_after_seconds: int | None = None
        try:
            await process_whatsapp_webhook(event["payload"])
        except asyncio.CancelledError:
            heartbeat_stop.set()
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
            try:
                await asyncio.shield(
                    store.finish_whatsapp_webhook(
                        event_id,
                        lease_token,
                        "Webhook worker interrupted",
                    )
                )
            except Exception:
                logger.exception("Could not release cancelled WhatsApp webhook event=%s", event_id)
            raise
        except Exception as exc:
            error_message = str(exc).strip()[:1000] or type(exc).__name__
            if isinstance(exc, WhatsAppInboundBusyError):
                retry_after_seconds = exc.retry_after_seconds
            logger.exception("WhatsApp webhook event failed event=%s", event_id)
        finally:
            heartbeat_stop.set()
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)

        finished = await store.finish_whatsapp_webhook(
            event_id,
            lease_token,
            error_message,
            retry_after_seconds=retry_after_seconds,
        )
        if not finished:
            logger.warning("WhatsApp webhook completion was fenced event=%s", event_id)


async def whatsapp_webhook_supervisor() -> None:
    interval = max(5, int(get_settings().whatsapp_webhook_recovery_interval_seconds))
    while True:
        try:
            recovery = await AdminStore().due_whatsapp_webhooks_detailed()
            recovered = set(recovery["recovered"])
            for event_id in recovery["due"]:
                schedule_whatsapp_webhook(
                    event_id,
                    replace_existing=event_id in recovered,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("WhatsApp webhook recovery sweep failed")
        await asyncio.sleep(interval)


async def cancel_whatsapp_webhook_tasks() -> None:
    tasks = [task for task in _webhook_tasks.values() if not task.done()]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
