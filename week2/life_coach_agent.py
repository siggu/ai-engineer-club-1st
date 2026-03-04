import asyncio

import dotenv

dotenv.load_dotenv()

import streamlit as st
from agents import (
    Agent,
    Runner,
    SQLiteSession,
    WebSearchTool,
)
from openai import OpenAI

client = OpenAI()

VECTOR_STORE_ID = "vs_69a7b82a73e88191be0eed0219f84df1"


def search_user_files(query: str) -> str:
    results = client.vector_stores.search(
        vector_store_id=VECTOR_STORE_ID,
        query=query,
        max_num_results=3,
    )
    if not results.data:
        return "관련 정보 없음"
    return "\n".join(item.content[0].text for item in results.data if item.content)


if "life_coach_agent" not in st.session_state:
    st.session_state["life_coach_agent"] = Agent(
        model="gpt-4o-mini",
        name="Life Coach Agent",
        instructions="""
        ### Role
        당신은 유저를 격려하는 라이프 코치 에이전트입니다.
        
        ### Response Procedure
        1. 유저 목표를 참고하여 웹 검색을 수행하세요.
        2. 유저 목표와 웹 검색 결과를 결합해 유저에게 개인화된 조언을 제공하세요.
        3. 마지막에 참고한 유저 목표와 웹 검색 결과 출처를 명시하세요.
        """,
        tools=[
            WebSearchTool(),
        ],
    )
life_coach_agent = st.session_state["life_coach_agent"]

if "session" not in st.session_state:
    st.session_state["session"] = SQLiteSession(
        "chat-history",
        "life_coach_agent.db",
    )

session = st.session_state["session"]


async def paint_history():
    messages = await session.get_items()

    for message in messages:
        if "role" not in message:
            continue
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.write(message["content"])
            else:
                if message.get("type") == "message":
                    st.write(message["content"][0]["text"])
        if "type" in message:
            if message["type"] == "web_search_call":
                with st.chat_message("ai"):
                    st.write("🔎 웹 검색...")
            elif message["type"] == "file_search_call":
                with st.chat_message("ai"):
                    st.write("📂 파일 검색...")


asyncio.run(paint_history())


def update_status(status_container, event):
    status_messages = {
        "response.web_search_call.in_progress": ("🔎 웹 검색 시작", "running"),
        "response.web_search_call.searching": ("🔎 웹 검색 중...", "running"),
        "response.web_search_call.completed": ("✅ 웹 검색 완료!", "complete"),
        "response.completed": (" ", "complete"),
        "response.file_search_call.in_progress": ("📂 파일 검색 시작", "running"),
        "response.file_search_call.searching": ("📂 파일 검색 중...", "running"),
        "response.file_search_call.completed": ("✅ 파일 검색 완료!", "complete"),
    }

    if event in status_messages:
        label, state = status_messages[event]
        status_container.update(label=label, state=state)


async def run_agent(message):
    with st.chat_message("ai"):
        status_container = st.status("📂 파일 검색 중...", expanded=False)

        file_info = search_user_files(message)
        status_container.update(label="✅ 파일 검색 완료!", state="complete")

        combined = f"유저 질문: {message}\n유저 파일 정보: {file_info}"

        status_container = st.status("🔎 웹 검색 중...", expanded=False)
        text_placeholder = st.empty()
        response = ""
        stream = Runner.run_streamed(life_coach_agent, combined, session=session)

        async for event in stream.stream_events():
            if event.type == "raw_response_event":
                update_status(status_container, event.data.type)
                if event.data.type == "response.output_text.delta":
                    response += event.data.delta
                    text_placeholder.write(response)


prompt = st.chat_input(
    "라이프 코치에게 말을 걸어보세요!",
    accept_file=True,
    file_type=["txt", "pdf"],
)

if prompt:
    if prompt.files:
        for file in prompt.files:
            with st.chat_message("ai"):
                with st.status("⌛ 파일 업로드 중...") as status:
                    uploaded_file = client.files.create(
                        file=file,
                        purpose="user_data",
                    )
                    status.update(label="⌛ 파일 접근 중...")
                    client.vector_stores.files.create(
                        vector_store_id=VECTOR_STORE_ID,
                        file_id=uploaded_file.id,
                    )
                    status.update(
                        label="✅ 파일 업로드 및 벡터화 완료!", state="complete"
                    )

    if prompt.text:
        with st.chat_message("human"):
            st.write(prompt.text)
        asyncio.run(run_agent(prompt.text))

with st.sidebar:
    reset = st.button("Reset Conversation")
    if reset:
        asyncio.run(session.clear_session())
    st.title("Life Coach Agent")
    st.markdown(
        """
        유저를 격려하는 라이프 코치 에이전트
        """
    )
    st.write(asyncio.run(session.get_items()))
