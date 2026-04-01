from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage


class AppState(TypedDict):
    # 입력 원본
    jd_raw: str
    resume_raw: str | None
    portfolio_raw: str | None

    # 파싱 결과
    jd_text: str
    resume_text: str | None
    portfolio_text: str | None

    # 입력 플래그
    has_resume: bool
    has_portfolio: bool

    # 공통 필드
    messages: Annotated[list[AnyMessage], add_messages]
    session_history: list[dict]
    answered_count: int
    weak_categories: list[str]
