import sqlite3
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from app.graph.state import AppState
from app.graph.nodes import input_parser


def build_graph(checkpointer):
    builder = StateGraph(AppState)

    # 노드 등록
    builder.add_node("input_parser", input_parser)

    # 엣지 연결
    builder.add_edge(START, "input_parser")
    builder.add_edge("input_parser", END)

    return builder.compile(checkpointer=checkpointer)


def create_default_graph():
    conn = sqlite3.connect("memory.db", check_same_thread=False)
    return build_graph(SqliteSaver(conn))
