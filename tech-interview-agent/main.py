from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages, MessagesState
from typing_extensions import TypedDict
from typing import Annotated
from langchain.chat_models import init_chat_model
from langchain_core.messages import AnyMessage
from dotenv import load_dotenv

load_dotenv()

# llm 설정
llm = init_chat_model("openai:gpt-5.4-mini")


# 챗봇 메세지 State 설정
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# 챗봇 노드 설정
def chatbot(state: State) -> State:
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


# StateGraph 설정
graph_builder = StateGraph(State)


# 노드 설정
graph_builder.add_node("chatbot", chatbot)


# 엣지 설정
graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", END)


# 그래프 컴파일
graph = graph_builder.compile()

print(graph.invoke({"messages": [{"role": "user", "content": "안녕하세요!"}]}))
