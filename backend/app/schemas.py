from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UploadRead(BaseModel):
    id: int
    file_path: str
    file_type: str
    extracted_text: str | None = None
    explanation: str | None = None
    processing_state: str = "success"
    processing_note: str | None = None
    extraction_method: str | None = None
    pages_processed: int | None = None
    total_pages: int | None = None
    truncated: bool = False
    created_at: datetime


class UploadCreateResponse(BaseModel):
    upload_id: int
    file_type: str
    processing_state: str = "success"
    processing_note: str | None = None
    extraction_method: str | None = None
    pages_processed: int | None = None
    total_pages: int | None = None
    truncated: bool = False
    created_at: datetime


class QuizScoreRequest(BaseModel):
    quiz_id: int
    answers: list[str]


class QuizScoreResponse(BaseModel):
    quiz_id: int
    score: float
    total_questions: int
    correct_answers: int


class FollowUpCreateRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class FollowUpMessageRead(BaseModel):
    id: int
    question: str
    response: str
    created_at: datetime


class FollowUpCreateResponse(BaseModel):
    conversation_id: int
    message_id: int
    question: str
    response: str
    created_at: datetime


class FollowUpHistoryResponse(BaseModel):
    conversation_id: int | None = None
    messages: list[FollowUpMessageRead] = Field(default_factory=list)
