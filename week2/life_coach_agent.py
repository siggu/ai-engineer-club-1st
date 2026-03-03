import asyncio

import dotenv

dotenv.load_dotenv()

import streamlit as st
from agents import Agent, Runner, SQLiteSession, WebSearchTool

if "agent" not in st.session_state:
    st.session_state['agent'] = Agent(
        name="Life Coach Agent",
        instructions="""
        당신은 유저를 격려하는 라이프 코치입니다. 
        
        **당신은 유저의 질문에 대해 반드시 아래 도구를 사용해야 합니다.**
        - WebSearchTool: 웹에서 정보를 검색할 수 있는 도구입니다. 유저가 질문을 하면, 당신은 **반드시** 이 도구를 사용하여 웹에서 정보를 검색하여 결과를 알려주어야 합니다.
        
        답변 마지막에 어디에서 정보를 찾았는지 출처를 명시해 주세요. 예시: (출처: 네이버 뉴스, https://news.naver.com/...)
        """,
        tools=[WebSearchTool()],
    )
agent = st.session_state["agent"]

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

asyncio.run(paint_history())

def update_status(status_container, event):
    status_messages = {
        "response.web_search_call.in_progress": ("🔎 웹 검색 시작", "running"),
        "response.web_search_call.searching": ("🔎 웹 검색 중...", "running"),
        "response.web_search_call.completed": ("✅ 웹 검색 완료!", "complete"),
        "response.completed": (" ", "complete"),
    }
    
    if event in status_messages:
        label, state = status_messages[event]
        status_container.update(label=label, state=state)

async def run_agent(message):
    with st.chat_message("ai"):
        status_container = st.status("⌛", expanded=False)
        text_placeholder = st.empty()
        response = ""
        stream = Runner.run_streamed(
            agent,
            message,
            session=session,
        )

        async for event in stream.stream_events():
            if event.type == "raw_response_event":
                update_status(status_container, event.data.type)
                if event.data.type == "response.output_text.delta":
                    response += event.data.delta
                    text_placeholder.write(response)

prompt = st.chat_input("라이프 코치에게 말을 걸어보세요!")

if prompt:
    with st.chat_message("human"):
        st.write(prompt)
    asyncio.run(run_agent(prompt))

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