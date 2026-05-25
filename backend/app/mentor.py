from collections.abc import AsyncGenerator
from .config import get_settings
from .claude import ClaudeService
from .embeddings import EmbeddingService
from .vector_store import VectorStore
from .prompts import MENTOR_SYSTEM_PROMPT, build_user_prompt, format_context
from .schemas import ChatRequest, ChatResponse
from .cache import Cache, cache_key


class MentorService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.claude = ClaudeService()
        self.embeddings = EmbeddingService()
        self.vector_store = VectorStore()
        self.cache = Cache()

    async def retrieve_sources(self, request: ChatRequest):
        vector = await self.embeddings.embed_one(request.message)
        return await self.vector_store.search(
            query_vector=vector,
            course=request.course,
            top_k=self.settings.top_k,
        )

    async def answer(self, request: ChatRequest) -> ChatResponse:
        key = cache_key(request.course, request.message, request.mode, request.level)
        if request.use_cache:
            cached = await self.cache.get(key)
            if cached:
                return ChatResponse(**cached)

        chunks = await self.retrieve_sources(request)
        context = format_context(chunks, self.settings.max_context_chars)
        user_prompt = build_user_prompt(
            course=request.course,
            level=request.level,
            mode=request.mode,
            message=request.message,
            context=context,
        )

        answer_text = await self.claude.answer_text(
            system_prompt=MENTOR_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        payload = ChatResponse(answer=answer_text, sources=chunks)
        await self.cache.set(key, payload.model_dump())
        return payload

    async def stream_answer(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        key = cache_key(request.course, request.message, request.mode, request.level)
        if request.use_cache:
            cached = await self.cache.get(key)
            if cached:
                # Stream cached answer to keep UI behavior identical.
                answer = cached.get("answer", "")
                for word in answer.split(" "):
                    yield f"data: {word} \n\n"
                yield "event: done\ndata: [DONE]\n\n"
                return

        chunks = await self.retrieve_sources(request)
        context = format_context(chunks, self.settings.max_context_chars)
        user_prompt = build_user_prompt(
            course=request.course,
            level=request.level,
            mode=request.mode,
            message=request.message,
            context=context,
        )

        try:
            full_answer: list[str] = []
            async for delta in self.claude.stream_text(
                system_prompt=MENTOR_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            ):
                full_answer.append(delta)
                # SSE format. Newlines in data need their own data prefix.
                safe_delta = str(delta).replace("\n", "\ndata: ")
                yield f"data: {safe_delta}\n\n"

            answer_text = "".join(full_answer)
            payload = ChatResponse(answer=answer_text, sources=chunks)
            await self.cache.set(key, payload.model_dump())
            yield "event: done\ndata: [DONE]\n\n"
        except Exception as exc:
            safe_error = str(exc).replace("\n", " ")
            yield f"event: error\ndata: {safe_error}\n\n"
