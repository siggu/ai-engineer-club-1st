from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class State(TypedDict):
    # 파일 선택
    selected_files: dict  # {"jd": "경로", "resume": None, "portfolio": None}

    # 입력 원본
    jd_raw: str
    resume_raw: str
    portfolio_raw: str

    # 파싱 결과
    jd_parsed: dict  # {"주요업무": [...], "자격요건": [...], "우대사항": [...]}
    resume_parsed: dict
    portfolio_parsed: dict

    # 웹 검색 결과
    search_results: list[dict]

    # 분석 결과
    skill_match: dict
    risk_points: list[str]
    jd_keywords: list[str]
    experience_highlights: list[str]

    # 면접 진행
    question_pool: list[dict]
    current_question: dict
    current_answer: str
    messages: Annotated[list, add_messages]
    current_score: float
    score_history: list[float]
    session_history: list[dict]
    weak_categories: list[str]
    answered_count: int
    total_questions: int
    interview_complete: bool
    retry_flag: bool
    interview_config: dict          # {"interview_mode": "sequential", "n_questions": 10, "coaching_mode": "full", "question_type": "mixed", "difficulty": "mixed"}
    answered_indices: list[int]     # free_order 모드에서 답변 완료된 question_pool 인덱스
    current_question_index: int     # free_order 모드에서 현재 선택된 인덱스
