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
    model: str                    # 사용할 LLM model_id (예: "openai:gpt-4o-mini")


DEFAULT_USER_CONFIG: UserConfig = {
    "total_questions": 5,
    "max_followup_depth": 2,
    "pressure_level": "medium",
    "followup_styles": ["deepdive", "counterexample"],
    "feedback_timing": "each",
    "show_model_answer": False,
    "model": "openai:gpt-5.4-mini",
}


class AbstractExpression(TypedDict):
    expression: str   # 원문에서 발견된 추상적 표현 (짧은 구/절)
    context: str      # 해당 표현이 사용된 원문 맥락 (한 문장)
    probe: str        # 이 표현을 파고드는 꼬리질문 예시


class AnalysisResult(TypedDict):
    skill_gaps: list[str]                        # JD 요구 but 이력서에 없거나 약함 → 약점 압박용
    strong_matches: list[str]                    # JD + 이력서 모두 강점 → 심화 탐색용
    contradiction_candidates: list[str]          # 이력서 주장 but 포트폴리오 미확인 → 모순 지적용
    shallow_mentions: list[str]                  # 이력서 단순 언급 기술 → 깊이 파고들기용
    abstract_expressions: list[AbstractExpression]  # 추상적 표현 → 꼬리질문 핵심 타깃
    key_topics: list[str]                        # 면접 핵심 주제 목록
    interview_strategy: str                      # 전체 면접 전략 요약 (자유 서술)


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

    # 분석 결과
    analysis_result: AnalysisResult

    # 면접 진행 상태
    current_question_depth: int   # 현재 꼬리질문 깊이 (0 = 기본 질문)
    current_base_question: str    # 현재 기본 질문 (꼬리질문 맥락 유지용)

    # 공통 필드
    messages: Annotated[list[AnyMessage], add_messages]
    session_history: list[dict]
    answered_count: int
    weak_categories: list[str]
