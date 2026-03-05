import asyncio
import base64

import dotenv

dotenv.load_dotenv()

import streamlit as st
from agents import (
    Agent,
    Runner,
    SQLiteSession,
    WebSearchTool,
    ImageGenerationTool,
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
        model="gpt-4o",
        name="Life Coach Agent",
        instructions="""
        당신은 유저를 격려하는 라이프 코치 에이전트입니다.
        
        당신은 아래 동작을 수행해야 합니다:
        
        1. 유저의 질문에 대한 조언, 팁, 동기부여 콘텐츠를 검색합니다.
        2. 유저의 질문과 관련된 파일이 있는지 검색합니다.
        3. 유저의 질문에 대한 답변을 합니다.
        
        **주의사항**:
        - 이미지를 생성해야 한다면 이미지를 생성해야 합니다.
        - 이미지 생성 예시: "목표 기반 비전 보드", "맞춤 메시지가 담긴 동기부여 포스터", "진행 상황의 시각적 표현" 등
        - 유저의 정보나 웹 검색 결과에 대한 출처를 간단히 명시해야 합니다.
        """,
        tools=[
            WebSearchTool(),
            ImageGenerationTool(
                tool_config={
                    "type": "image_generation",
                    "quality": "low",
                    "output_format": "jpeg",
                    "moderation": "low",
                    "partial_images": 1,
                }
            ),
        ],
    )
life_coach_agent = st.session_state["life_coach_agent"]

class FixedSQLiteSession(SQLiteSession):
    async def get_items(self, limit=None):
        items = await super().get_items(limit=limit)
        for item in items:
            if isinstance(item, dict) and item.get("type") == "image_generation_call":
                item.pop("action", None)
        return items


if "session" not in st.session_state:
    st.session_state["session"] = FixedSQLiteSession(
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
                content = message["content"]
                if isinstance(content, str) and "\n유저 파일 정보:" in content:
                    content = content.split("\n유저 파일 정보:")[0].replace(
                        "유저 질문: ", ""
                    )
                st.write(content)
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
            elif message["type"] == "image_generation_call":
                image = base64.b64decode(message["result"])
                with st.chat_message("ai"):
                    st.image(image)


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
        "response.image_generation_call.in_progress": (
            "🎨 이미지 생성 시작",
            "running",
        ),
        "response.image_generation_call.completed": (
            "✅ 이미지 생성 완료!",
            "complete",
        ),
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
        image_placeholder = st.empty()
        response = ""
        stream = Runner.run_streamed(life_coach_agent, combined, session=session)

        async for event in stream.stream_events():
            if event.type == "raw_response_event":
                update_status(status_container, event.data.type)
                if event.data.type == "response.output_text.delta":
                    response += event.data.delta
                    text_placeholder.write(response)
                elif event.data.type == "response.image_generation_call.partial_image":
                    image = base64.b64decode(event.data.partial_image_b64)
                    image_placeholder.image(image)


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
