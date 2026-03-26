from typing import Any, Optional
from pydantic import BaseModel


class AnswerRequest(BaseModel):
    answer: str


class SessionResponse(BaseModel):
    session_id: str
    status: str
    question: dict[str, Any]


class AnswerResponse(BaseModel):
    status: str                           # "in_progress" | "complete"
    question: Optional[dict[str, Any]] = None
    report: Optional[dict[str, Any]] = None
