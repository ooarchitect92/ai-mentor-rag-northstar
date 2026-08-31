import asyncio

from app.mentor import MentorService, remove_next_steps
from app.schemas import ChatRequest, SourceChunk


class FakeCache:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value):
        self.values[key] = value

    async def get_text(self, key):
        return self.values.get(key)

    async def set_text(self, key, value, ttl_seconds):
        self.values[key] = value

    async def delete(self, key):
        self.values.pop(key, None)


class FakeHistory:
    def __init__(self):
        self.records = []

    async def find_first_answer(self, *, course, question):
        for record in self.records:
            if (
                record["course"] == course
                and record["question"] == question
                and record["stage"] == 1
                and record["reusable"]
            ):
                return record
        return None

    async def append(self, **record):
        self.records.append(record)


class FakeEmbeddings:
    async def embed_one(self, text):
        return [1.0]


class FakeStore:
    def __init__(self, sources):
        self.sources = sources

    async def search(self, **kwargs):
        return self.sources


class FakeApprovedAnswers:
    def __init__(self, answer=None):
        self.answer = answer

    async def find_published_answer(self, course, question):
        if self.answer and course == "CMA" and question == "Explain variance analysis":
            return {"id": "approved-1", "answer": self.answer}
        return None


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    async def answer_text(self, **kwargs):
        self.calls += 1
        return self.responses.pop(0)


def source(score):
    return SourceChunk(
        source_id="northstar-cma",
        title="NorthStar Academy CMA lesson",
        course="CMA",
        doc_type="lesson",
        text="Variance analysis compares actual results with planned results.",
        score=score,
    )


def service_with(sources, llm_responses):
    service = MentorService()
    service.cache = FakeCache()
    service.embeddings = FakeEmbeddings()
    service.vector_store = FakeStore(sources)
    service.llm = FakeLLM(llm_responses)
    service.policy_llm = service.llm
    service.history = FakeHistory()
    return service


def request():
    return ChatRequest(course="CMA", message="Explain variance analysis", use_cache=False)


def test_next_step_sections_and_closing_offers_are_removed():
    answer = (
        "The complete explanation.\n\n"
        "*Next Steps*\n"
        "Try another question.\n\n"
        "Would you like another example?"
    )

    assert remove_next_steps(answer) == "The complete explanation."


def test_published_answer_is_exact_and_bypasses_generation():
    service = service_with([], [])
    service.admin_store = FakeApprovedAnswers("The approved exact wording.")

    first = asyncio.run(service.answer(request()))
    second = asyncio.run(service.answer(request().model_copy(update={"student_id": "whatsapp:919999999999", "use_cache": True})))

    assert first.answer == "The approved exact wording."
    assert second.answer == first.answer
    assert service.llm.calls == 0


def test_low_relevance_context_does_not_limit_in_course_answer():
    service = service_with(
        [source(0.2)],
        ["IN_SCOPE", "Variance analysis is explained fully.", "ALLOW"],
    )

    response = asyncio.run(service.answer(request()))

    assert response.answer == "Variance analysis is explained fully."
    assert response.sources == []
    assert service.llm.calls == 3


def test_out_of_course_text_question_is_refused_before_answer_generation():
    service = service_with([], ["OUT_OF_SCOPE"])

    response = asyncio.run(service.answer(request()))

    assert response.answer == service.course_refusal("CMA")
    assert response.sources == []
    assert service.llm.calls == 1
    assert service.cache.values == {}


def test_use_cache_false_generates_without_writing_reusable_history():
    service = service_with(
        [],
        ["IN_SCOPE", "A valid enrolled-course answer.", "ALLOW"],
    )

    response = asyncio.run(service.answer(request()))

    assert response.answer == "A valid enrolled-course answer."
    assert service.cache.values == {}
    assert service.history.records == []


def test_repeat_cycle_reuses_first_answer_then_deepens_and_clarifies():
    service = service_with(
        [],
        [
            "IN_SCOPE", "First answer", "ALLOW",
            "IN_SCOPE", "Second detailed answer", "ALLOW",
            "IN_SCOPE", "Third deeper answer", "ALLOW",
            "IN_SCOPE",
        ],
    )
    # This case verifies reusable-answer behavior when no published knowledge
    # base is active. When retrieval is enabled, fresh indexed content must
    # intentionally take precedence over historical generated answers.
    service.settings = service.settings.model_copy(update={"course_retrieval_enabled": False})
    repeated = ChatRequest(
        student_id="student-one",
        course="CMA",
        message="Explain variance analysis",
        use_cache=True,
    )

    answers = [asyncio.run(service.answer(repeated)).answer for _ in range(4)]

    assert answers[:3] == ["First answer", "Second detailed answer", "Third deeper answer"]
    assert "What exactly would you like me to explain" in answers[3]
    assert [record["stage"] for record in service.history.records] == [1, 2, 3, 4]

    other_student = repeated.model_copy(update={"student_id": "student-two"})
    reused = asyncio.run(service.answer(other_student))

    assert reused.answer == "First answer"
    assert service.llm.calls == 10


def test_clarification_reply_generates_focused_answer_and_resets_cycle():
    service = service_with(
        [],
        [
            "IN_SCOPE", "First", "ALLOW",
            "IN_SCOPE", "Second", "ALLOW",
            "IN_SCOPE", "Third", "ALLOW",
            "IN_SCOPE",
            "IN_SCOPE", "Focused clarification answer", "ALLOW",
        ],
    )
    repeated = ChatRequest(
        student_id="student-one",
        course="CMA",
        message="Explain variance analysis",
        use_cache=True,
    )
    for _ in range(4):
        asyncio.run(service.answer(repeated))

    clarification = repeated.model_copy(update={"message": "Show the calculation with numbers"})
    response = asyncio.run(service.answer(clarification))

    assert response.answer == "Focused clarification answer"
    assert service.history.records[-1]["kind"] == "clarification_answer"
    assert service.history.records[-1]["clarification"] == "Show the calculation with numbers"


def test_output_guard_fails_closed_and_removes_sources():
    service = service_with([source(0.8)], ["IN_SCOPE", "Unsupported outside answer", "BLOCK"])

    response = asyncio.run(service.answer(request()))

    assert response.answer == service.course_refusal("CMA")
    assert response.sources == []
    assert service.llm.calls == 3


def test_grounded_policy_approved_answer_is_returned():
    service = service_with(
        [source(0.8)],
        ["IN_SCOPE", "Variance analysis compares actual and planned results.", "ALLOW"],
    )

    response = asyncio.run(service.answer(request()))

    assert response.answer == "Variance analysis compares actual and planned results."
    assert response.sources == []


def test_in_course_image_can_be_answered_without_matching_chunk():
    service = service_with(
        [],
        [
            "IN_SCOPE",
            "*Direct Answer*\nThe calculation is explained step by step.",
            "ALLOW",
        ],
    )

    response = asyncio.run(service.answer_image(request()))

    assert "calculation is explained" in response.answer
    assert response.sources == []
    assert service.llm.calls == 3


def test_out_of_course_image_is_refused_before_answer_generation():
    service = service_with([], ["OUT_OF_SCOPE"])

    response = asyncio.run(service.answer_image(request()))

    assert response.answer == service.image_refusal("CMA")
    assert response.sources == []
    assert service.llm.calls == 1


def test_image_output_guard_blocks_disallowed_answer():
    service = service_with([], ["IN_SCOPE", "An outside-company answer", "BLOCK"])

    response = asyncio.run(service.answer_image(request()))

    assert response.answer == service.image_refusal("CMA")
    assert response.sources == []
