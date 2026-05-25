import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, ORJSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from .auth import require_admin_token
from .chunking import chunk_text
from .config import get_settings
from .documents import read_text_file
from .embeddings import EmbeddingService
from .mentor import MentorService
from .schemas import ChatRequest, ChatResponse, IngestResult, WhatsAppMenuRequest, WhatsAppStartRequest
from .vector_store import VectorStore
from .whatsapp import WhatsAppClient, normalize_wa_id, process_whatsapp_webhook, verify_meta_signature


settings = get_settings()
app = FastAPI(
    title="AI Mentor RAG API",
    description="RAG-based AI mentor for CMA / CPA / ACCA / EA training institutes",
    version="1.0.0",
    default_response_class=ORJSONResponse,
)

frontend_dir = Path("/app/frontend")
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


@app.get("/")
async def home():
    index = frontend_dir / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "AI Mentor RAG API is running. Open /docs for API docs."}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "collection": settings.qdrant_collection,
        "llm_provider": "anthropic",
        "llm_model": settings.anthropic_model,
        "embedding_provider": settings.embedding_provider,
        "whatsapp_configured": bool(
            settings.whatsapp_use_mock
            or ((settings.whatsapp_access_token or settings.whatsapp_token) and settings.whatsapp_phone_number_id)
        ),
        "whatsapp_mock": settings.whatsapp_use_mock,
    }


@app.get("/v1/whatsapp/webhook")
async def verify_whatsapp_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return Response(content=hub_challenge or "", media_type="text/plain")

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid WhatsApp webhook verification token",
    )


@app.post("/v1/whatsapp/webhook")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    raw_body = await request.body()
    if not verify_meta_signature(raw_body, request.headers.get("x-hub-signature-256")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid WhatsApp webhook signature",
        )

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        ) from exc

    background_tasks.add_task(process_whatsapp_webhook, payload)
    return {"status": "accepted"}


@app.post("/v1/admin/whatsapp/send-program-menu", dependencies=[Depends(require_admin_token)])
async def send_whatsapp_program_menu(request: WhatsAppMenuRequest):
    client = WhatsAppClient()
    to = normalize_wa_id(request.to)
    meta_response = await client.send_program_menu(to)
    return {"status": "sent", "to": to, "menu": "program", "meta_response": meta_response}


@app.post("/v1/admin/whatsapp/send-hi", dependencies=[Depends(require_admin_token)])
async def send_whatsapp_hi(request: WhatsAppStartRequest):
    client = WhatsAppClient()
    to = normalize_wa_id(request.to)
    template_name = request.template_name or settings.whatsapp_start_template_name
    language_code = request.language_code or settings.whatsapp_start_template_language
    meta_response = await client.send_start_message(
        to=to,
        template_name=template_name,
        language_code=language_code,
    )
    return {
        "status": "sent",
        "to": to,
        "template_name": template_name,
        "language_code": language_code,
        "next_step": "Customer must reply to this WhatsApp template. Their reply opens the menu flow.",
        "meta_response": meta_response,
    }


@app.post("/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    service = MentorService()
    return await service.answer(request)


@app.post("/v1/chat/stream")
async def chat_stream(request: ChatRequest):
    service = MentorService()
    return StreamingResponse(
        service.stream_answer(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/v1/admin/ingest/files", response_model=IngestResult, dependencies=[Depends(require_admin_token)])
async def ingest_files(
    files: list[UploadFile] = File(...),
    course: str = Form("GENERAL"),
    doc_type: str = Form("lesson"),
):
    embedder = EmbeddingService()
    store = VectorStore()
    total_chunks = 0

    for uploaded in files:
        suffix = Path(uploaded.filename or "document.txt").suffix or ".txt"
        with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await uploaded.read())
            tmp_path = Path(tmp.name)

        try:
            text = read_text_file(tmp_path)
            chunks = chunk_text(text)
            texts = [c.text for c in chunks]
            vectors = await embedder.embed_many(texts)
            total_chunks += await store.upsert_chunks(
                texts=texts,
                embeddings=vectors,
                title=uploaded.filename or "Uploaded document",
                source_id=uploaded.filename or tmp_path.name,
                course=course,
                doc_type=doc_type,
            )
        finally:
            tmp_path.unlink(missing_ok=True)

    return IngestResult(
        files=len(files),
        chunks=total_chunks,
        collection=settings.qdrant_collection,
    )
