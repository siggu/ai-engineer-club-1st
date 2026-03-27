from langgraph.types import Send

from .state import State


def dispatch_parsing(state: State) -> list[Send]:
    cfg   = state.get("interview_config", {})
    sends = []
    if state.get("jd_raw"):
        sends.append(Send("parse_doc", {"doc_type": "jd",        "raw": state["jd_raw"],        "interview_config": cfg}))
    if state.get("resume_raw"):
        sends.append(Send("parse_doc", {"doc_type": "resume",    "raw": state["resume_raw"],    "interview_config": cfg}))
    if state.get("portfolio_raw"):
        sends.append(Send("parse_doc", {"doc_type": "portfolio", "raw": state["portfolio_raw"], "interview_config": cfg}))
    return sends if sends else [Send("merge_parsed", {})]


def route_analyzer(state: State) -> str:
    messages = state.get("messages", [])
    if messages and hasattr(messages[-1], "tool_calls") and messages[-1].tool_calls:
        return "search"
    return "done"


def route_after_eval(state: State) -> str:
    """evaluator 실행 후 다음 노드를 결정한다.

    완료 판정:
      - sequential: answered_count >= total_questions
      - free_order : len(answered_indices) >= len(question_pool)

    미완료 시:
      - coaching_mode == "simple" → 다음 질문으로 바로 이동 ("continue")
      - coaching_mode == "full"   → 점수에 따라 hint / similar / followup
    """
    cfg            = state.get("interview_config", {})
    interview_mode = cfg.get("interview_mode", "sequential")
    coaching_mode  = cfg.get("coaching_mode", "full")

    # ── 완료 판정 ────────────────────────────────────────────────────
    if interview_mode == "free_order":
        answered_indices = state.get("answered_indices", [])
        total            = len(state.get("question_pool", []))
        if total > 0 and len(answered_indices) >= total:
            return "done"
    else:
        if state.get("answered_count", 0) >= state.get("total_questions", 1):
            return "done"

    # ── 코칭 모드 분기 ───────────────────────────────────────────────
    if coaching_mode == "simple":
        return "continue"

    score = state.get("current_score", 0.0)
    if score < 5.0:
        return "hint"
    elif score < 8.0:
        return "similar"
    else:
        return "followup"
