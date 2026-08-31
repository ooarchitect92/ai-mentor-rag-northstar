import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from .admin_store import AdminStore, VersionConflictError
from .auth import require_admin_token
from .config import (
    RuntimeConfigurationConflictError,
    get_settings,
    public_runtime_settings,
    read_system_prompt,
    runtime_configuration_version,
    update_runtime_configuration,
    validate_runtime_setting_values,
)
from .documents import SUPPORTED_EXTENSIONS, read_text_file
from .prompts import COURSE_MENTOR_SYSTEM_PROMPT
from .schemas import (
    ApprovedAnswerCreate,
    ApprovedAnswerUpdate,
    ChatRequest,
    ConfigurationUpdate,
    Course,
    DocumentType,
    FeedbackUpdate,
    KnowledgeDocumentUpdate,
    ModelTestRequest,
    TrainingJobRequest,
    WhatsAppMessagingUpdate,
    WhatsAppPreviewRequest,
)
from .mentor import MentorService
from .llm import MentorLLMService
from .training import schedule_training_job
from .vector_store import VectorStore
from .whatsapp import MODE_BY_VALUE, enrollment_source, format_whatsapp_answer, split_feedback_marker


logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/v1/admin", dependencies=[Depends(require_admin_token)])


def _store() -> AdminStore:
    return AdminStore()


def _secret_status(settings) -> dict[str, bool]:
    return {
        "nvidia_api_key": bool(settings.nvidia_api_key),
        "gemini_api_key": bool(settings.gemini_api_key),
        "anthropic_api_key": bool(settings.anthropic_api_key),
        "openai_api_key": bool(settings.openai_api_key),
        "whatsapp_access_token": bool(settings.whatsapp_access_token or settings.whatsapp_token),
        "whatsapp_app_secret": bool(settings.whatsapp_app_secret or settings.meta_app_secret),
    }


def _validate_provider_credentials(settings) -> None:
    configured = {
        "nvidia": bool(settings.nvidia_api_key),
        "gemini": bool(settings.gemini_api_key),
        "anthropic": bool(settings.anthropic_api_key),
    }
    required = {settings.mentor_provider}
    if settings.mentor_fallback_provider != "none":
        required.add(settings.mentor_fallback_provider)
    if settings.mentor_policy_provider == "gemini":
        required.add("gemini")
    missing = sorted(provider for provider in required if not configured[provider])
    if missing:
        names = ", ".join(f"{provider.upper()}_API_KEY" for provider in missing)
        raise ValueError(f"Configure {names} in the deployment environment before selecting these providers")


def _validate_setting_bounds(values: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(values)
    numeric_bounds = {
        "nvidia_temperature": (0, 2),
        "nvidia_top_p": (0.01, 1),
        "nvidia_max_tokens": (64, 16_384),
        "nvidia_reasoning_budget": (0, 16_384),
        "gemini_max_output_tokens": (64, 16_384),
        "anthropic_max_tokens": (64, 16_384),
        "cache_ttl_seconds": (60, 2_592_000),
        "top_k": (1, 25),
        "max_context_chars": (500, 50_000),
        "minimum_retrieval_score": (0, 1),
        "whatsapp_max_reply_chars": (500, 4_000),
    }
    for key, (minimum, maximum) in numeric_bounds.items():
        if key in normalized and not minimum <= float(normalized[key]) <= maximum:
            raise ValueError(f"{key} must be between {minimum} and {maximum}")

    if "whatsapp_feedback_number" in normalized:
        digits = "".join(character for character in str(normalized["whatsapp_feedback_number"]) if character.isdigit())
        if digits and not 8 <= len(digits) <= 15:
            raise ValueError("whatsapp_feedback_number must be a valid international WhatsApp number")
        normalized["whatsapp_feedback_number"] = digits
    if "whatsapp_feedback_prefill" in normalized:
        message = str(normalized["whatsapp_feedback_prefill"]).strip()
        has_marker, description = split_feedback_marker(message)
        copy = description if has_marker else message
        if not copy:
            raise ValueError("whatsapp_feedback_prefill must include a short message after the FEEDBACK command")
        canonical = f"FEEDBACK\n{copy}"
        if not 8 <= len(canonical) <= 500:
            raise ValueError("whatsapp_feedback_prefill must contain between 8 and 500 characters")
        # The command is protocol, not editable copy. Canonicalizing it here
        # prevents a dashboard edit from silently breaking inbound routing.
        normalized["whatsapp_feedback_prefill"] = canonical
    return validate_runtime_setting_values(normalized)


@router.get("/overview")
async def admin_overview():
    result = await _store().overview()
    settings = get_settings()
    result.update(
        {
            "retrieval_enabled": settings.course_retrieval_enabled,
            "embedding_provider": settings.embedding_provider,
            "collection": settings.qdrant_collection,
            "feedback_number_configured": bool(settings.whatsapp_feedback_number),
            "environment": settings.app_environment,
            "mentor_provider": settings.mentor_provider,
            "mentor_model": settings.nvidia_model if settings.mentor_provider == "nvidia" else (
                settings.gemini_model if settings.mentor_provider == "gemini" else settings.anthropic_model
            ),
            "reasoning_enabled": settings.nvidia_enable_thinking if settings.mentor_provider == "nvidia" else False,
        }
    )
    return result


async def _whatsapp_status_payload() -> dict[str, Any]:
    settings = get_settings()
    queue = await _store().whatsapp_queue_summary()
    latest_created_at = queue.get("latest_inbound_message_at")
    try:
        latest_created = datetime.fromisoformat(str(latest_created_at))
        if latest_created.tzinfo is None:
            latest_created = latest_created.replace(tzinfo=UTC)
        recent_inbound = latest_created >= datetime.now(UTC) - timedelta(minutes=15)
    except (TypeError, ValueError):
        recent_inbound = False
    token_configured = bool((settings.whatsapp_access_token or settings.whatsapp_token).strip())
    phone_configured = bool(settings.whatsapp_phone_number_id.strip())
    signature_configured = bool((settings.whatsapp_app_secret or settings.meta_app_secret).strip())
    relay_configured = bool(settings.whatsapp_relay_token.strip())
    callback_url = settings.whatsapp_webhook_callback_url.strip()
    callback_path = urlparse(callback_url).path.rstrip("/").lower() if callback_url else ""
    direct_callback = callback_path.endswith(("/v1/whatsapp/webhook", "/v1/whatsapp/ziplin/webhook")) or not callback_url
    delivery_mode = "direct" if direct_callback else "existing_webhook_relay"
    public_base_url = settings.northstar_public_base_url.strip().rstrip("/")
    public_origin = urlparse(public_base_url)
    stable_ingress_configured = bool(
        public_origin.scheme == "https"
        and public_origin.hostname
        and not public_origin.hostname.casefold().endswith(".trycloudflare.com")
    )
    routing_ready = bool(
        settings.whatsapp_verify_token.strip() and signature_configured
        if direct_callback
        else relay_configured and stable_ingress_configured
    )
    return {
        "enabled": settings.whatsapp_messaging_enabled,
        "configuration_version": runtime_configuration_version(settings),
        "inbound_ready": routing_ready,
        "routing_ready": routing_ready,
        "recent_inbound": recent_inbound,
        "delivery_mode": delivery_mode,
        "outbound_ready": bool(token_configured and phone_configured),
        "access_token_configured": token_configured,
        "signature_configured": signature_configured,
        "relay_configured": relay_configured,
        "phone_number_id": settings.whatsapp_phone_number_id,
        "business_account_id": settings.whatsapp_business_account_id,
        "graph_api_version": settings.whatsapp_graph_api_version,
        "webhook_callback_url": callback_url,
        "public_base_url": public_base_url,
        "stable_ingress_configured": stable_ingress_configured,
        "direct_callback_path": "/v1/whatsapp/ziplin/webhook",
        "relay_path": "/v1/whatsapp/ziplin/relay",
        "relay_destination_url": (
            f"{public_base_url}/v1/whatsapp/ziplin/relay" if stable_ingress_configured else ""
        ),
        "feedback_number": settings.whatsapp_feedback_number,
        "open_cma_access": settings.whatsapp_open_cma_access,
        "default_course": settings.whatsapp_default_course,
        "default_mode": settings.whatsapp_default_mode,
        "default_level": settings.whatsapp_default_level,
        "enrollment_source": enrollment_source(),
        "queue": queue,
    }


@router.get("/whatsapp/status")
async def whatsapp_status():
    return await _whatsapp_status_payload()


@router.put("/whatsapp/messaging")
async def update_whatsapp_messaging(request: WhatsAppMessagingUpdate):
    try:
        settings, _, version = update_runtime_configuration(
            {"whatsapp_messaging_enabled": request.enabled},
            system_prompt=None,
            expected_version=request.version,
            default_prompt=COURSE_MENTOR_SYSTEM_PROMPT,
        )
    except RuntimeConfigurationConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await _store().record_audit(
        "whatsapp.messaging_enabled" if settings.whatsapp_messaging_enabled else "whatsapp.messaging_paused",
        "whatsapp_configuration",
        str(version),
        {"enabled": settings.whatsapp_messaging_enabled},
    )
    return await _whatsapp_status_payload()


@router.get("/audit")
async def list_audit_events(
    search: str = Query(default="", max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return await _store().list_audit_events(
        search=search.strip(),
        limit=limit,
        offset=offset,
    )


@router.get("/analytics")
async def usage_analytics(days: int = Query(default=30, ge=1, le=365)):
    return await _store().analytics(days)


@router.post("/model/test")
async def test_configured_model(request: ModelTestRequest):
    settings = get_settings()
    try:
        _validate_provider_credentials(settings)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    service = MentorLLMService()
    provider = settings.mentor_provider
    model = settings.nvidia_model if provider == "nvidia" else (
        settings.gemini_model if provider == "gemini" else settings.anthropic_model
    )
    started = time.perf_counter()
    try:
        answer = await service.answer_text(
            system_prompt=(
                "You are a concise NorthStar Academy model-health assistant. "
                "Answer the test prompt directly in no more than two sentences."
            ),
            user_prompt=request.prompt.strip(),
        )
    except Exception as exc:
        logger.exception("Configured model health test failed provider=%s", provider)
        raise HTTPException(status_code=502, detail=f"{provider.title()} model test failed: {type(exc).__name__}") from exc
    finally:
        await service.aclose()
    latency_ms = round((time.perf_counter() - started) * 1000)
    await _store().record_audit(
        "model.test",
        "llm_provider",
        provider,
        {"model": model, "latency_ms": latency_ms, "success": True},
    )
    return {
        "status": "ok",
        "provider": provider,
        "model": model,
        "latency_ms": latency_ms,
        "thinking_enabled": settings.nvidia_enable_thinking if provider == "nvidia" else False,
        "answer": answer,
    }


@router.post("/mentor/whatsapp-preview")
async def preview_whatsapp_answer(request: WhatsAppPreviewRequest):
    """Run the same mentor and formatter used by the WhatsApp webhook."""
    settings = get_settings()
    service = MentorService()
    started = time.perf_counter()
    try:
        chat_request = ChatRequest(
            student_id="admin:whatsapp-preview",
            course=request.course,
            mode=request.mode,
            level=request.level,
            message=request.question,
            use_cache=False,
        )
        approved = await _store().find_published_answer(request.course, request.question)
        response = await service.answer(chat_request)
        mode_option = MODE_BY_VALUE[request.mode]
        whatsapp_answer = format_whatsapp_answer(response.answer, request.course, mode_option)
    except Exception as exc:
        logger.exception("WhatsApp mentor preview failed")
        raise HTTPException(status_code=502, detail=f"Mentor preview failed: {type(exc).__name__}") from exc
    finally:
        await service.aclose()
    latency_ms = round((time.perf_counter() - started) * 1000)
    await _store().record_audit(
        "mentor.whatsapp_preview",
        "approved_answer" if approved else "rag_preview",
        str(approved["id"]) if approved else None,
        {"course": request.course, "mode": request.mode, "latency_ms": latency_ms},
    )
    return {
        "answer": response.answer,
        "whatsapp_answer": whatsapp_answer,
        "course": request.course,
        "mode": request.mode,
        "level": request.level,
        "latency_ms": latency_ms,
        "provider": settings.mentor_provider,
        "model": settings.nvidia_model if settings.mentor_provider == "nvidia" else (
            settings.gemini_model if settings.mentor_provider == "gemini" else settings.anthropic_model
        ),
        "exact_match": bool(approved),
        "approved_answer_id": approved["id"] if approved else None,
    }


@router.get("/approved-answers")
async def list_approved_answers(
    course: Course | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return await _store().list_approved_answers(course=course, limit=limit, offset=offset)


@router.post("/approved-answers", status_code=status.HTTP_201_CREATED)
async def create_approved_answer(request: ApprovedAnswerCreate):
    try:
        return await _store().create_approved_answer(request.course, request.question, request.answer)
    except VersionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/approved-answers/{answer_id}")
async def update_approved_answer(answer_id: str, request: ApprovedAnswerUpdate):
    try:
        result = await _store().update_approved_answer(
            answer_id, request.course, request.question, request.answer, request.version
        )
    except VersionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Approved answer not found")
    return result


@router.post("/approved-answers/{answer_id}/publish")
async def publish_approved_answer(answer_id: str):
    result = await _store().publish_approved_answer(answer_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Approved answer not found")
    return result


@router.delete("/approved-answers/{answer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_approved_answer(answer_id: str):
    if not await _store().delete_approved_answer(answer_id):
        raise HTTPException(status_code=404, detail="Approved answer not found")


@router.get("/knowledge/documents")
async def list_knowledge_documents(
    search: str = Query(default="", max_length=200),
    course: Course | None = None,
    document_status: str | None = Query(default=None, alias="status", pattern="^(draft|queued|indexing|indexed|failed|deleting)$"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return await _store().list_documents(
        search=search.strip(),
        course=course,
        status=document_status,
        limit=limit,
        offset=offset,
    )


async def _extract_upload(uploaded: UploadFile, maximum_bytes: int) -> tuple[str, str]:
    original_name = Path(uploaded.filename or "document.txt").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"{original_name}: supported types are TXT, Markdown, PDF, and DOCX",
        )

    total = 0
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(delete=False, suffix=suffix) as temporary:
            temporary_path = Path(temporary.name)
            while chunk := await uploaded.read(1024 * 1024):
                total += len(chunk)
                if total > maximum_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"{original_name}: file exceeds the {maximum_bytes // (1024 * 1024)} MB limit",
                    )
                temporary.write(chunk)
        if total == 0:
            raise HTTPException(status_code=422, detail=f"{original_name}: file is empty")
        try:
            content = (await asyncio.to_thread(read_text_file, temporary_path)).strip()
        except Exception as exc:
            logger.warning("Document parsing failed filename=%s error=%s", original_name, type(exc).__name__)
            raise HTTPException(status_code=422, detail=f"{original_name}: the document could not be read") from exc
        if not content:
            raise HTTPException(status_code=422, detail=f"{original_name}: no readable text was found")
        if len(content) > 2_000_000:
            raise HTTPException(status_code=413, detail=f"{original_name}: extracted text is too large")
        return original_name, content
    finally:
        await uploaded.close()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


@router.post("/knowledge/documents", status_code=status.HTTP_201_CREATED)
async def create_knowledge_documents(
    files: list[UploadFile] = File(...),
    course: Course = Form(...),
    doc_type: DocumentType = Form("lesson"),
):
    settings = get_settings()
    if not files or len(files) > settings.admin_upload_max_files:
        raise HTTPException(
            status_code=422,
            detail=f"Upload between 1 and {settings.admin_upload_max_files} files at a time",
        )
    extracted = [await _extract_upload(uploaded, settings.admin_upload_max_bytes) for uploaded in files]
    store = _store()
    items = await store.create_documents(
        [
            {
                "title": Path(filename).stem[:300],
                "filename": filename,
                "course": course,
                "doc_type": doc_type,
                "content": content,
            }
            for filename, content in extracted
        ]
    )
    return {"items": items, "total": len(items)}


@router.get("/knowledge/documents/{document_id}")
async def read_knowledge_document(document_id: str):
    document = await _store().get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Knowledge document not found")
    return document


@router.put("/knowledge/documents/{document_id}")
async def update_knowledge_document(document_id: str, request: KnowledgeDocumentUpdate):
    current = await _store().get_document(document_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Knowledge document not found")
    if current["status"] in {"queued", "indexing"}:
        raise HTTPException(status_code=409, detail="Wait for the active training job before editing this document")
    try:
        document = await _store().update_document(
            document_id,
            title=request.title.strip(),
            course=request.course,
            doc_type=request.doc_type,
            content=request.content.strip(),
            expected_version=request.version,
        )
    except VersionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if document is None:
        raise HTTPException(status_code=404, detail="Knowledge document not found")
    return document


@router.delete("/knowledge/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_document(document_id: str):
    store = _store()
    try:
        document = await store.prepare_document_delete(document_id)
    except VersionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if document is None:
        raise HTTPException(status_code=404, detail="Knowledge document not found")
    vector_store: VectorStore | None = None
    try:
        # An edited document is a draft but may still have a previously published index.
        if document.get("indexed_at") or int(document.get("chunk_count") or 0) > 0:
            vector_store = VectorStore()
            await vector_store.delete_source(document_id)
    except Exception:
        await store.set_document_status(
            document_id,
            document["status"],
            chunk_count=int(document.get("chunk_count") or 0),
            error_message=document.get("error_message"),
        )
        raise
    finally:
        if vector_store is not None:
            try:
                await vector_store.client.close()
            except Exception:
                logger.exception("Could not close vector client after deleting document=%s", document_id)
    await store.delete_document(document_id)
    return None


@router.get("/training/jobs")
async def list_training_jobs(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return await _store().list_training_jobs(limit=limit, offset=offset)


@router.get("/training/jobs/{job_id}")
async def read_training_job(job_id: str):
    job = await _store().get_training_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Training job not found")
    return job


@router.post("/training/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_training_job(request: TrainingJobRequest):
    document_ids = list(dict.fromkeys(request.document_ids))
    try:
        job = await _store().create_training_job(document_ids)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Knowledge document not found: {exc.args[0]}") from exc
    except VersionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    schedule_training_job(job["id"])
    return job


@router.post("/training/jobs/{job_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_training_job(job_id: str):
    store = _store()
    previous = await store.get_training_job(job_id)
    if previous is None:
        raise HTTPException(status_code=404, detail="Training job not found")
    if previous["status"] not in {"failed", "partial"}:
        raise HTTPException(status_code=409, detail="Only failed or partial training jobs can be retried")

    available_ids: list[str] = []
    for document_id in previous["document_ids"]:
        document = await store.get_document(str(document_id))
        if document is not None and document["status"] != "deleting":
            available_ids.append(str(document_id))
    if not available_ids:
        raise HTTPException(status_code=409, detail="No source documents from this job are still available")

    try:
        job = await store.create_training_job(available_ids)
    except VersionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    schedule_training_job(job["id"])
    return job


@router.get("/feedback")
async def list_feedback(
    feedback_status: str | None = Query(
        default=None,
        alias="status",
        pattern="^(open|reviewing|resolved|dismissed)$",
    ),
    category: str | None = Query(default=None, pattern="^(change|error|other)$"),
    search: str = Query(default="", max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return await _store().list_feedback(
        status=feedback_status,
        category=category,
        search=search.strip(),
        limit=limit,
        offset=offset,
    )


@router.patch("/feedback/{feedback_id}")
async def update_feedback(feedback_id: str, request: FeedbackUpdate):
    feedback = await _store().update_feedback(
        feedback_id,
        status=request.status,
        category=request.category,
        admin_notes=request.admin_notes.strip(),
    )
    if feedback is None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return feedback


@router.get("/feedback/{feedback_id}/attachment")
async def read_feedback_attachment(feedback_id: str):
    store = _store()
    feedback = await store.get_feedback(feedback_id)
    if feedback is None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    path = store.attachment_path(feedback)
    if path is None:
        raise HTTPException(status_code=404, detail="Feedback screenshot not found")
    return FileResponse(
        path,
        media_type=feedback.get("attachment_mime_type") or "application/octet-stream",
        filename=path.name,
        content_disposition_type="inline",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.get("/configuration")
async def read_configuration():
    settings = get_settings()
    return {
        "version": runtime_configuration_version(settings),
        "settings": public_runtime_settings(settings),
        "system_prompt": read_system_prompt(COURSE_MENTOR_SYSTEM_PROMPT),
        "secret_status": _secret_status(settings),
    }


@router.put("/configuration")
async def update_configuration(request: ConfigurationUpdate):
    try:
        validated = _validate_setting_bounds(request.settings)
        candidate = get_settings().model_copy(update=validated)
        _validate_provider_credentials(candidate)
        settings, system_prompt, version = update_runtime_configuration(
            validated,
            system_prompt=request.system_prompt,
            expected_version=request.version,
            default_prompt=COURSE_MENTOR_SYSTEM_PROMPT,
        )
    except RuntimeConfigurationConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    logger.info("Admin runtime configuration updated fields=%s", sorted(validated))
    await _store().record_audit(
        "configuration.updated",
        "runtime_configuration",
        str(version),
        {"fields": sorted(validated), "system_prompt_updated": request.system_prompt is not None},
    )
    return {
        "version": version,
        "settings": public_runtime_settings(settings),
        "system_prompt": system_prompt,
        "secret_status": _secret_status(settings),
    }
