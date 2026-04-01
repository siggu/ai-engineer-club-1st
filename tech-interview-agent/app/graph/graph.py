import sqlite3
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from app.graph.state import AppState
from app.graph.nodes import input_parser, user_config, analyzer


def build_graph(checkpointer):
    builder = StateGraph(AppState)

    # 노드 등록
    builder.add_node("input_parser", input_parser)
    builder.add_node("user_config", user_config)
    builder.add_node("analyzer", analyzer)

    # input_parser, user_config 병렬 실행
    builder.add_edge(START, "input_parser")
    builder.add_edge(START, "user_config")

    # input_parser 완료 후 analyzer 실행
    builder.add_edge("input_parser", "analyzer")

    # analyzer, user_config 둘 다 끝나면 END (이후 chatbot 연결 시 변경)
    builder.add_edge("analyzer", END)
    builder.add_edge("user_config", END)

    return builder.compile(checkpointer=checkpointer)


def create_default_graph():
    conn = sqlite3.connect("memory.db", check_same_thread=False)
    return build_graph(SqliteSaver(conn))
