from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage


class UserConfig(TypedDict):
    total_questions: int          # 기본 질문 수 (기본값: 5)
    max_followup_depth: int       # 꼬리질문 최대 깊이 (기본값: 2)
    pressure_level: str           # "low" | "medium" | "high"
    followup_styles: list[str]    # ["contradiction", "deepdive", "counterexample", "practical"]
    feedback_timing: str          # "each" | "final"
    show_model_answer: bool       # 모범 답안 공개 여부


DEFAULT_USER_CONFIG: UserConfig = {
    "total_questions": 5,
    "max_followup_depth": 2,
    "pressure_level": "medium",
    "followup_styles": ["deepdive", "counterexample"],
    "feedback_timing": "each",
    "show_model_answer": False,
}


class AppState(TypedDict):
    # 유저 설정
    user_config: UserConfig

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

    # 면접 진행 상태
    current_question_depth: int   # 현재 꼬리질문 깊이 (0 = 기본 질문)
    current_base_question: str    # 현재 기본 질문 (꼬리질문 맥락 유지용)

    # 공통 필드
    messages: Annotated[list[AnyMessage], add_messages]
    session_history: list[dict]
    answered_count: int
    weak_categories: list[str]
