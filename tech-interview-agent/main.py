import sqlite3
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages, MessagesState
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import interrupt, Command
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


@tool
def get_answer(question: str):
    """
    질문에 대한 답변을 하도록 하세요.\n
    최종 답변 전에 반드시 답변을 받으세요.
    """
    feedback = interrupt(f"질문에 대한 답변을 해주세요. \n 질문: \n{question}")
    return feedback


llm_with_tools = llm.bind_tools(tools=[web_search_tool, get_answer])


# 챗봇 노드 생성
def chatbot(state: State) -> State:
    system_prompt = {
        "role": "system",
        "content": """당신은 AI 개발자를 채용하는 기술 면접관입니다.

        규칙:
        1. 대화가 시작되면 AI 관련 기술 면접 질문을 하나 생성하세요. (최신 AI 기술에 대해 질문하려면 `web_search_tool`을 사용하세요.)
        2. 반드시 `get_answer` 도구를 호출해 지원자의 답변을 받으세요. `question` 인자에는 당신이 생성한 면접 질문을 넣으세요.
        3. 답변을 받은 후 정확도와 깊이를 평가해 피드백을 제공하세요.
        4. 절대로 당신이 직접 질문에 답하지 마세요.""",
    }
    response = llm_with_tools.invoke([system_prompt] + state["messages"])
    return {"messages": [response]}


# tool 노드 생성
tool_node = ToolNode(
    tools=[web_search_tool, get_answer],
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

# config 설정
config = {"configurable": {"thread_id": "4"}, "recursion_limit": 10}


# 첫 실행
result = graph.invoke(
    {"messages": [{"role": "user", "content": "네. 정리해주세요."}]},
    config=config,
)


for message in result["messages"]:
    message.pretty_print()

# interrupt 이후 사용자 입력 받기, Command로 재개
user_answer = input("답변을 입력하세요.")
result = graph.invoke(Command(resume=user_answer), config=config)

for message in result["messages"]:
    message.pretty_print()
