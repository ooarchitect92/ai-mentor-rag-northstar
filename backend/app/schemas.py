from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


Course = Literal["CMA", "CPA", "CFA", "ACCA", "CS", "EA"]
DocumentType = Literal["lesson", "notes", "faq", "quiz", "job_hunt", "policy", "other"]


class ChatRequest(BaseModel):
    student_id: str = Field(default="anonymous")
    course: Course = Field(default="CMA")
    message: str = Field(min_length=1, max_length=6000)
    level: Literal["beginner", "intermediate", "advanced"] = "beginner"
    mode: Literal["teach", "quiz", "revise", "job_hunt", "doubt_solving"] = "teach"
    use_cache: bool = True


class SourceChunk(BaseModel):
    source_id: str
    title: str
    course: str
    doc_type: str
    text: str
    score: float | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]


class IngestResult(BaseModel):
    files: int
    chunks: int
    collection: str


class WhatsAppMenuRequest(BaseModel):
    to: str = Field(min_length=8, max_length=20)


class WhatsAppStartRequest(BaseModel):
    to: str = Field(min_length=8, max_length=20)
    template_name: str | None = Field(default=None, min_length=1, max_length=512)
    language_code: str | None = Field(default=None, min_length=2, max_length=20)


class WhatsAppEnrollmentRequest(BaseModel):
    course: Course


class WhatsAppEnrollmentResponse(BaseModel):
    phone: str
    courses: list[Course]
    course: Course | None = None
    source: Literal["excel", "google_sheet", "redis"] = "redis"


class WhatsAppMessagingUpdate(BaseModel):
    enabled: bool
    version: int = Field(ge=0)


class KnowledgeDocumentUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    course: Course
    doc_type: DocumentType
    content: str = Field(min_length=1, max_length=2_000_000)
    version: int = Field(ge=1)

    @field_validator("title", "content")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value cannot be blank")
        return normalized


class TrainingJobRequest(BaseModel):
    document_ids: list[str] = Field(min_length=1, max_length=100)


class ModelTestRequest(BaseModel):
    prompt: str = Field(
        default="In one sentence, explain why variance analysis is useful to a management accountant.",
        min_length=5,
        max_length=500,
    )


class WhatsAppPreviewRequest(BaseModel):
    course: Course = "CMA"
    mode: Literal["teach", "quiz", "revise", "job_hunt", "doubt_solving"] = "doubt_solving"
    level: Literal["beginner", "intermediate", "advanced"] = "beginner"
    question: str = Field(min_length=2, max_length=6000)

    @field_validator("question")
    @classmethod
    def reject_blank_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Question cannot be blank")
        return normalized


class ApprovedAnswerCreate(BaseModel):
    course: Course
    question: str = Field(min_length=2, max_length=6000)
    answer: str = Field(min_length=2, max_length=20_000)

    @field_validator("question", "answer")
    @classmethod
    def reject_blank_approved_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value cannot be blank")
        return normalized


class ApprovedAnswerUpdate(ApprovedAnswerCreate):
    version: int = Field(ge=1)


class FeedbackUpdate(BaseModel):
    status: Literal["open", "reviewing", "resolved", "dismissed"]
    category: Literal["change", "error", "other"]
    admin_notes: str = Field(default="", max_length=6000)


class ConfigurationUpdate(BaseModel):
    version: int = Field(ge=0)
    settings: dict[str, Any] = Field(default_factory=dict)
    system_prompt: str | None = Field(default=None, min_length=100, max_length=20_000)
