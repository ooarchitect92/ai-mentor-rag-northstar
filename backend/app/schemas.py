from pydantic import BaseModel, Field
from typing import Literal


Course = Literal["CMA", "CPA", "ACCA", "EA", "GENERAL"]


class ChatRequest(BaseModel):
    student_id: str = Field(default="anonymous")
    course: Course = Field(default="GENERAL")
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
