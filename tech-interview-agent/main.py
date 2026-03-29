import sqlite3
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages, MessagesState
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict
from typing import Annotated
from langchain.chat_models import init_chat_model
from langchain_core.messages import AnyMessage
from langchain_core.tools import tool
from dotenv import load_dotenv
from langchain_tavily import TavilySearch

load_dotenv()

# llm 설정
llm = init_chat_model("openai:gpt-5.4-mini")

conn = sqlite3.connect("memory.db", check_same_thread=False)


# 챗봇 메세지 State 설정
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# Tool 설정
web_search_tool = TavilySearch(
    max_results=3,
    description=("웹 서치 기능이 필요할 때 사용합니다."),
)


llm_with_tools = llm.bind_tools(tools=[web_search_tool])


# 챗봇 노드 생성
def chatbot(state: State) -> State:
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}


# tool 노드 생성
tool_node = ToolNode(
    tools=[web_search_tool],
)

# StateGraph 설정
graph_builder = StateGraph(State)


# 노드 설정
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("tools", tool_node)


# 엣지 설정
graph_builder.add_edge(START, "chatbot")
graph_builder.add_conditional_edges("chatbot", tools_condition)
graph_builder.add_edge("tools", "chatbot")


# 그래프 컴파일
graph = graph_builder.compile(
    checkpointer=SqliteSaver(conn),
)

print(
    graph.invoke(
        {"messages": [{"role": "user", "content": "제가 뭐라고 질문했었죠"}]},
        config={
            "configurable": {
                "thread_id": "1",
            },
            "recursion_limit": 10,
        },
    )
)
