from langgraph.types import Send

from .state import State


def dispatch_parsing(state: State) -> list[Send]:
    sends = []
    if state.get("jd_raw"):
        sends.append(Send("parse_doc", {"doc_type": "jd",        "raw": state["jd_raw"]}))
    if state.get("resume_raw"):
        sends.append(Send("parse_doc", {"doc_type": "resume",    "raw": state["resume_raw"]}))
    if state.get("portfolio_raw"):
        sends.append(Send("parse_doc", {"doc_type": "portfolio", "raw": state["portfolio_raw"]}))
    return sends if sends else [Send("merge_parsed", {})]


def route_analyzer(state: State) -> str:
    messages = state.get("messages", [])
    if messages and hasattr(messages[-1], "tool_calls") and messages[-1].tool_calls:
        return "search"
    return "done"


def route_by_score(state: State) -> str:
    score = state.get("current_score", 0.0)
    if score >= 8.0:
        return "followup"
    elif score >= 5.0:
        return "similar"
    else:
        return "hint"


def check_completion(state: State) -> str:
    if state.get("answered_count", 0) >= state.get("total_questions", 1):
        return "done"
    return "continue"
