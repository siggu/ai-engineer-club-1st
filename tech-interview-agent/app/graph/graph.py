import sqlite3
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from app.graph.state import AppState
from app.graph.nodes import input_parser, user_config


def build_graph(checkpointer):
    builder = StateGraph(AppState)

    # 노드 등록
    builder.add_node("input_parser", input_parser)
    builder.add_node("user_config", user_config)

    # input_parser, user_config 병렬 실행
    builder.add_edge(START, "input_parser")
    builder.add_edge(START, "user_config")

    # 둘 다 끝나면 END (이후 chatbot 노드 추가 시 변경)
    builder.add_edge("input_parser", END)
    builder.add_edge("user_config", END)

    return builder.compile(checkpointer=checkpointer)


def create_default_graph():
    conn = sqlite3.connect("memory.db", check_same_thread=False)
    return build_graph(SqliteSaver(conn))
