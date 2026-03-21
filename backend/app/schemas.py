import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


# ── Auth ──────────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None
    business_name: str = Field(min_length=1, max_length=200)
    industry: str | None = None
    size: str | None = None
    stage: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Business ──────────────────────────────────────────────────────────────────

class BusinessOut(BaseModel):
    id: uuid.UUID
    name: str
    industry: str | None
    size: str | None
    stage: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class BusinessUpdate(BaseModel):
    name: str | None = None
    industry: str | None = None
    size: str | None = None
    stage: str | None = None


# ── User ──────────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    business_id: uuid.UUID
    business: BusinessOut

    class Config:
        from_attributes = True


# ── Knowledge Base ────────────────────────────────────────────────────────────

class KnowledgeBaseOut(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    data: dict
    phase: str
    gaps: list
    updated_at: datetime

    class Config:
        from_attributes = True


class KBUpdate(BaseModel):
    data: dict
    phase: str | None = None
    gaps: list | None = None


# ── Conversations ─────────────────────────────────────────────────────────────

class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut] = []

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID | None = None  # None = create new
    message: str = Field(min_length=1, max_length=10000)


class ChatSources(BaseModel):
    kb_categories: list[str] = []   # KB categories that had data
    doc_chunks: int = 0             # number of RAG chunks used


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    reply: str
    knowledge_updates: dict
    phase: str
    knowledge_gaps: list[str]
    sources: ChatSources = ChatSources()


# ── Trust / Health ─────────────────────────────────────────────────────────────

class HealthSnapshotResponse(BaseModel):
    kb_fill_pct: float              # 0-100, percentage of KB categories filled
    filled_categories: list[str]
    missing_categories: list[str]
    phase: str
    total_documents: int
    total_chunks: int


class TestQuestion(BaseModel):
    id: int
    question: str
    category: str                   # which KB category this tests


class TestGenerateResponse(BaseModel):
    questions: list[TestQuestion]


class TestAnswerItem(BaseModel):
    question_id: int
    answer: str


class TestScoreRequest(BaseModel):
    questions: list[TestQuestion]
    answers: list[TestAnswerItem]


class TestResultItem(BaseModel):
    question_id: int
    question: str
    your_answer: str
    buddy_answer: str
    score: int                      # 1-5
    feedback: str


class TestScoreResponse(BaseModel):
    results: list[TestResultItem]
    overall_score: float            # average 1-5
    summary: str
