from collections.abc import AsyncGenerator
import hashlib
import json
import logging
import re
from .config import get_settings, read_system_prompt
from .llm import MentorLLMService
from .gemini import GeminiService
from .embeddings import EmbeddingService
from .vector_store import VectorStore
from .prompts import (
    COURSE_MENTOR_SYSTEM_PROMPT,
    NORTHSTAR_IMMUTABLE_SAFETY_POLICY,
    build_course_check_prompt,
    build_course_output_guard_prompt,
    build_course_user_prompt,
    format_context,
)
from .schemas import ChatRequest, ChatResponse
from .cache import Cache
from .question_history import QuestionAnswerStore, normalize_question_text, question_key
from .admin_store import AdminStore


logger = logging.getLogger("uvicorn.error")


UNWANTED_CLOSING_HEADINGS = {
    "next step",
    "next steps",
    "next study step",
    "practice task",
    "follow-up",
    "follow-up question",
    "follow up",
    "follow up question",
    "try this",
    "what to do next",
}


def remove_next_steps(answer: str) -> str:
    """Remove unsolicited action-oriented closings from generated or stored answers."""
    kept: list[str] = []
    for line in answer.strip().splitlines():
        heading = re.sub(r"^[\s#*_\-]+|[\s#*_:.-]+$", "", line).casefold()
        if heading in UNWANTED_CLOSING_HEADINGS:
            break
        kept.append(line)

    cleaned = "\n".join(kept).rstrip()
    paragraphs = re.split(r"\n\s*\n", cleaned)
    while paragraphs and re.match(
        r"^\s*(would you like|if you(?:'d| would)? like|if you want|try (?:this|solving)|send me|you can now)\b",
        paragraphs[-1],
        flags=re.IGNORECASE,
    ):
        paragraphs.pop()
    return "\n\n".join(paragraphs).strip()


class MentorService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm = MentorLLMService()
        self.policy_llm = GeminiService() if self.settings.mentor_policy_provider == "gemini" else self.llm
        self.embeddings = EmbeddingService()
        self.vector_store = VectorStore()
        self.cache = Cache()
        self.history = QuestionAnswerStore(self.settings.question_answer_file)
        self.admin_store = AdminStore()

    async def aclose(self) -> None:
        """Release per-request network clients without affecting the response path."""
        resources = (
            ("answer cache", self.cache.aclose),
            ("embedding client", self.embeddings.aclose),
            ("vector client", self.vector_store.client.close),
            ("mentor client", self.llm.aclose),
        )
        for label, closer in resources:
            try:
                await closer()
            except Exception:
                logger.exception("Could not close %s", label)

    async def retrieve_sources(self, request: ChatRequest):
        if not self.settings.course_retrieval_enabled:
            return []
        vector = await self.embeddings.embed_one(request.message)
        return await self.vector_store.search(
            query_vector=vector,
            course=request.course,
            top_k=self.settings.top_k,
        )

    @staticmethod
    def refusal() -> str:
        return "I can only help with your active course using NorthStar Academy course material."

    @staticmethod
    def image_refusal(course: str) -> str:
        return (
            f"I could read the image, but it does not appear to contain a {course} course question. "
            f"Please send a clear {course} question or MCQ screenshot."
        )

    @staticmethod
    def course_refusal(course: str) -> str:
        return (
            f"This question is not related to your active {course} course. "
            f"Please send a {course} course question."
        )

    def is_refusal(self, answer: str, course: str) -> bool:
        """Refusals are policy decisions and must be re-evaluated on every request."""
        return answer in {
            self.refusal(),
            self.course_refusal(course),
            self.image_refusal(course),
        }

    def grounded_sources(self, chunks):
        if not self.settings.strict_grounding:
            return chunks
        return [
            chunk
            for chunk in chunks
            if chunk.score is not None and chunk.score >= self.settings.minimum_retrieval_score
        ]

    async def _policy_answer_text(self, *, system_prompt: str, user_prompt: str) -> str:
        try:
            return await self.policy_llm.answer_text(system_prompt=system_prompt, user_prompt=user_prompt)
        except Exception:
            if self.policy_llm is self.llm:
                raise
            logger.exception("Fast policy provider failed; trying primary mentor provider")
            return await self.llm.answer_text(system_prompt=system_prompt, user_prompt=user_prompt)

    async def image_question_is_in_course(self, request: ChatRequest) -> bool:
        try:
            verdict = await self._policy_answer_text(
                system_prompt="Classify the student question against the active course. Return only the required label.",
                user_prompt=build_course_check_prompt(
                    course=request.course,
                    question=request.message,
                ),
            )
            normalized = verdict.strip().upper()
            logger.info("Course relevance check course=%s verdict=%s", request.course, normalized[:32])
            return normalized == "IN_SCOPE"
        except Exception:
            logger.exception("Course relevance check failed course=%s", request.course)
            return False

    async def image_answer_is_allowed(self, *, request: ChatRequest, answer: str) -> bool:
        try:
            verdict = await self._policy_answer_text(
                system_prompt="Enforce the supplied output policy. Return only ALLOW or BLOCK.",
                user_prompt=build_course_output_guard_prompt(
                    course=request.course,
                    question=request.message,
                    answer=answer,
                ),
            )
            normalized = verdict.strip().upper()
            logger.info("Course answer guard course=%s verdict=%s", request.course, normalized[:32])
            return normalized == "ALLOW"
        except Exception:
            logger.exception("Course answer guard failed course=%s", request.course)
            return False

    async def answer_course_question(
        self,
        request: ChatRequest,
        scope_refusal: str,
        detail_instruction: str = "Give a complete descriptive answer with all required reasoning steps.",
    ) -> ChatResponse:
        """Answer any in-course question; retrieved material is optional enhancement only."""
        if not await self.image_question_is_in_course(request):
            return ChatResponse(answer=scope_refusal, sources=[])

        try:
            chunks = self.grounded_sources(await self.retrieve_sources(request))
        except Exception:
            logger.exception("Optional course-context retrieval failed course=%s", request.course)
            chunks = []

        context = format_context(chunks, self.settings.max_context_chars)
        answer_text = await self.llm.answer_text(
            system_prompt=(
                NORTHSTAR_IMMUTABLE_SAFETY_POLICY
                + "\n\nEditable mentor instructions:\n"
                + read_system_prompt(COURSE_MENTOR_SYSTEM_PROMPT)
            ),
            user_prompt=build_course_user_prompt(
                course=request.course,
                level=request.level,
                mode=request.mode,
                message=request.message,
                context=context,
                detail_instruction=detail_instruction,
            ),
        )
        answer_text = remove_next_steps(answer_text)
        if not answer_text or not await self.image_answer_is_allowed(request=request, answer=answer_text):
            return ChatResponse(answer=scope_refusal, sources=[])

        # Course material may improve the answer internally, but students see only the answer.
        return ChatResponse(answer=answer_text, sources=[])

    @staticmethod
    def _student_fingerprint(student_id: str) -> str:
        return hashlib.sha256(student_id.strip().encode("utf-8")).hexdigest()[:24]

    def _repeat_key(self, request: ChatRequest, original_question: str | None = None) -> str:
        key = question_key(request.course, original_question or request.message)
        student = self._student_fingerprint(request.student_id)
        return f"mentor:repeat:{student}:{key}"

    def _clarification_key(self, request: ChatRequest) -> str:
        student = self._student_fingerprint(request.student_id)
        return f"mentor:clarification:{student}:{request.course}"

    async def _repeat_count(self, request: ChatRequest, original_question: str | None = None) -> int:
        raw = await self.cache.get_text(self._repeat_key(request, original_question))
        try:
            value = int(raw or "0")
        except ValueError:
            value = 0
        return value if 0 <= value <= 4 else 0

    async def _set_repeat_count(
        self,
        request: ChatRequest,
        value: int,
        original_question: str | None = None,
    ) -> None:
        await self.cache.set_text(
            self._repeat_key(request, original_question),
            str(value),
            ttl_seconds=self.settings.question_repeat_ttl_seconds,
        )

    @staticmethod
    def _detail_instruction(stage: int) -> str:
        if stage == 2:
            return (
                "This is the student's second request for this question. Generate a fresh answer that is "
                "more detailed than the first: add definitions, reasoning, steps, an example, and common mistakes."
            )
        if stage == 3:
            return (
                "This is the student's third request for this question. Generate a fresh, substantially deeper "
                "answer: explain underlying principles, every calculation or assumption, an additional example, "
                "exam interpretation, and common traps while remaining WhatsApp-friendly."
            )
        return "Give a complete descriptive answer with all required reasoning steps and a clear example where useful."

    @staticmethod
    def _clarification_prompt(course: str) -> str:
        return (
            f"You have asked this {course} question several times. What exactly would you like me to explain "
            "more clearly—its basic concept, a specific calculation, why an option is correct, an example, "
            "or an exam-solving method? Reply with the exact part you want help with."
        )

    async def _answer_pending_clarification(
        self,
        request: ChatRequest,
        pending: dict,
        scope_refusal: str,
    ) -> ChatResponse | None:
        original = str(pending.get("question") or "").strip()
        if not original:
            await self.cache.delete(self._clarification_key(request))
            return None
        if normalize_question_text(request.message) == normalize_question_text(original):
            return ChatResponse(answer=self._clarification_prompt(request.course), sources=[])

        combined = request.model_copy(
            update={
                "message": (
                    f"Original {request.course} question:\n{original}\n\n"
                    f"The student now says this is the exact part they want clarified:\n{request.message}"
                )
            }
        )
        payload = await self.answer_course_question(
            combined,
            scope_refusal,
            detail_instruction=(
                "Answer the student's stated clarification directly and precisely. Connect it to the original "
                "question, explain every necessary step, and include a focused example when useful."
            ),
        )
        if self.is_refusal(payload.answer, request.course):
            return payload

        await self.history.append(
            course=request.course,
            question=original,
            clarification=request.message,
            answer=payload.answer,
            stage=4,
            kind="clarification_answer",
            reusable=False,
        )
        await self.cache.delete(self._clarification_key(request))
        await self.cache.delete(self._repeat_key(request, original))
        return payload

    async def _answer_with_history(self, request: ChatRequest, *, image: bool) -> ChatResponse:
        scope_refusal = self.image_refusal(request.course) if image else self.course_refusal(request.course)
        if not request.use_cache:
            return await self.answer_course_question(request, scope_refusal)

        pending_raw = await self.cache.get_text(self._clarification_key(request))
        if pending_raw:
            try:
                pending = json.loads(pending_raw)
            except json.JSONDecodeError:
                await self.cache.delete(self._clarification_key(request))
            else:
                pending_answer = await self._answer_pending_clarification(request, pending, scope_refusal)
                if pending_answer is not None:
                    return pending_answer

        prior_count = await self._repeat_count(request)
        stage = (prior_count % 4) + 1

        if stage == 1:
            stored = await self.history.find_first_answer(course=request.course, question=request.message)
            # A published knowledge base must take precedence over historical generated answers.
            if stored and not self.settings.course_retrieval_enabled:
                await self._set_repeat_count(request, 1)
                logger.info("Reusable question answer served course=%s stage=1", request.course)
                return ChatResponse(answer=remove_next_steps(str(stored["answer"])), sources=[])

        if stage == 4:
            if not await self.image_question_is_in_course(request):
                return ChatResponse(answer=scope_refusal, sources=[])
            clarification_prompt = self._clarification_prompt(request.course)
            await self.history.append(
                course=request.course,
                question=request.message,
                answer=clarification_prompt,
                stage=4,
                kind="clarification_prompt",
                reusable=False,
            )
            await self.cache.set_text(
                self._clarification_key(request),
                json.dumps({"question": request.message}, ensure_ascii=False),
                ttl_seconds=self.settings.question_repeat_ttl_seconds,
            )
            await self._set_repeat_count(request, 4)
            return ChatResponse(answer=clarification_prompt, sources=[])

        payload = await self.answer_course_question(
            request,
            scope_refusal,
            detail_instruction=self._detail_instruction(stage),
        )
        if not self.is_refusal(payload.answer, request.course):
            await self.history.append(
                course=request.course,
                question=request.message,
                answer=payload.answer,
                stage=stage,
                kind="answer",
                reusable=stage == 1,
            )
            await self._set_repeat_count(request, stage)
        return payload

    async def answer_image(self, request: ChatRequest) -> ChatResponse:
        """Answer an extracted image question through the same reusable history cycle."""
        approved = await self.admin_store.find_published_answer(request.course, request.message)
        if approved:
            return ChatResponse(answer=remove_next_steps(str(approved["answer"])), sources=[])
        return await self._answer_with_history(request, image=True)

    async def answer(self, request: ChatRequest) -> ChatResponse:
        # Published answers are the deterministic contract between the dashboard
        # and WhatsApp. They bypass generation but not course isolation.
        approved = await self.admin_store.find_published_answer(request.course, request.message)
        if approved:
            return ChatResponse(answer=remove_next_steps(str(approved["answer"])), sources=[])
        return await self._answer_with_history(request, image=False)

    async def stream_answer(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        try:
            # Validate the complete response before releasing any text to the student.
            payload = await self.answer(request)
            for word in payload.answer.split(" "):
                safe_word = word.replace("\n", "\ndata: ")
                yield f"data: {safe_word} \n\n"
            yield "event: done\ndata: [DONE]\n\n"
        except Exception as exc:
            safe_error = str(exc).replace("\n", " ")
            yield f"event: error\ndata: {safe_error}\n\n"
