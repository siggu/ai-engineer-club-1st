from typing import Any, Optional
from pydantic import BaseModel


class AnswerRequest(BaseModel):
    answer: str
    selected_index: Optional[int] = None   # free_order 모드에서 선택한 질문 인덱스


class SessionResponse(BaseModel):
    session_id: str
    status: str
    question: dict[str, Any]


class AnswerResponse(BaseModel):
    status: str                           # "in_progress" | "complete"
    question: Optional[dict[str, Any]] = None
    report: Optional[dict[str, Any]] = None
