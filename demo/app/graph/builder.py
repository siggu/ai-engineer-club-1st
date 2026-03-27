import os
import sqlite3
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from .state import State
from .nodes import (
    read_files, parse_doc, merge_parsed,
    analyzer, tool_node,
    questioner, interviewer,
    hint_provider, similar_q, followup_gen,
    evaluator, report_gen,
)
from .edges import dispatch_parsing, route_analyzer, route_after_eval

graph_builder = StateGraph(State)

# ── 노드 추가 ────────────────────────────────────────────────────────
graph_builder.add_node("read_files",    read_files)
graph_builder.add_node("parse_doc",     parse_doc)
graph_builder.add_node("merge_parsed",  merge_parsed)
graph_builder.add_node("analyzer",      analyzer)
graph_builder.add_node("tool_node",     tool_node)
graph_builder.add_node("questioner",    questioner)
graph_builder.add_node("interviewer",   interviewer)
graph_builder.add_node("hint_provider", hint_provider)
graph_builder.add_node("similar_q",     similar_q)
graph_builder.add_node("followup_gen",  followup_gen)
graph_builder.add_node("evaluator",     evaluator)
graph_builder.add_node("report_gen",    report_gen)

# ── 엣지 추가 ────────────────────────────────────────────────────────
# 파싱 단계: Send API 병렬 실행
graph_builder.add_edge(START, "read_files")
graph_builder.add_conditional_edges("read_files", dispatch_parsing, ["parse_doc", "merge_parsed"])
graph_builder.add_edge("parse_doc",    "merge_parsed")
graph_builder.add_edge("merge_parsed", "analyzer")

# 분석 단계: tool_node 루프
graph_builder.add_conditional_edges(
    "analyzer", route_analyzer,
    {"search": "tool_node", "done": "questioner"},
)
graph_builder.add_edge("tool_node", "analyzer")

# 면접 단계
# interviewer → evaluator (항상): 답변 수집 후 즉시 채점
graph_builder.add_edge("questioner",    "interviewer")
graph_builder.add_edge("interviewer",   "evaluator")

# evaluator → route_after_eval: 완료/코칭/다음 문항 분기
graph_builder.add_conditional_edges(
    "evaluator", route_after_eval,
    {
        "done":     "report_gen",
        "continue": "interviewer",
        "hint":     "hint_provider",
        "similar":  "similar_q",
        "followup": "followup_gen",
    },
)

# 코칭 노드 → 다시 면접
graph_builder.add_edge("hint_provider", "interviewer")
graph_builder.add_edge("similar_q",     "interviewer")
graph_builder.add_edge("followup_gen",  "interviewer")

graph_builder.add_edge("report_gen", END)

# ── 컴파일 ───────────────────────────────────────────────────────────
os.makedirs("data", exist_ok=True)
conn = sqlite3.connect("data/sessions.db", check_same_thread=False)
checkpointer = SqliteSaver(conn)
graph = graph_builder.compile(checkpointer=checkpointer)
