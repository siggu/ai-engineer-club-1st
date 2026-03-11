import asyncio
import streamlit as st
from openai import OpenAI
from models import UserAccountContext
from agents import Runner, SQLiteSession
from my_agents.triage_agent import triage_agent
from my_agents.menu_agent import menu_agent
from my_agents.order_agent import order_agent
from my_agents.reservation_agent import reservation_agent
from my_agents.complaint_agent import complaint_agent

import dotenv


dotenv.load_dotenv()


client = OpenAI()

AGENTS = {
    "Triage Agent": triage_agent,
    "Menu Agent": menu_agent,
    "Order Agent": order_agent,
    "Reservation Agent": reservation_agent,
    "Complaint Agent": complaint_agent,
}

user_account_context = UserAccountContext(
    customer_id=1,
    name="Jeongmok",
)

if "session" not in st.session_state:
    st.session_state["session"] = SQLiteSession(
        "chat-history",
        "restaurant_agent.db",
    )
session = st.session_state["session"]


if "current_agent" not in st.session_state:
    st.session_state["current_agent"] = triage_agent

if "handoff_info" not in st.session_state:
    st.session_state.handoff_info = None


async def paint_history():
    messages = await session.get_items()
    for message in messages:
        if "role" in message:
            if message["role"] == "system":
                st.info(message["content"])
                continue

            with st.chat_message(message["role"]):
                if message["role"] == "user":
                    st.write(message["content"])
                else:
                    if message["type"] == "message":
                        st.write(message["content"][0]["text"].replace("$", "\$"))


asyncio.run(paint_history())


async def run_agent(message, is_handoff_continuation=False):
    with st.chat_message("ai"):
        text_placeholder = st.empty()
        response = ""
        handoff_detected = False

        try:
            stream = Runner.run_streamed(
                st.session_state.current_agent,
                message,
                session=session,
                context=user_account_context,
            )

            async for event in stream.stream_events():
                if event.type not in ["raw_response_event"]:
                    print(f"DEBUG - Event type: {event.type}")

                if event.type == "raw_response_event":
                    if event.data.type == "response.output_text.delta":
                        response += event.data.delta
                        text_placeholder.write(response.replace("$", "\$"))

                elif event.type == "agent_updated_stream_event":
                    new_agent = AGENTS.get(event.new_agent.name, event.new_agent)
                    if st.session_state.current_agent.name != new_agent.name:
                        st.session_state.current_agent = new_agent
                        st.write(f"🔄 **{new_agent.name}**로 연결되었습니다.")
                        text_placeholder = st.empty()
                        response = ""

        except Exception as e:
            st.error(f"Error: {e}")


async def handle_user_message(message):
    """사용자 메시지 처리"""
    # 원본 메시지를 pending_handoff에 저장 (handoff 시 사용)
    if "pending_handoff" not in st.session_state:
        st.session_state.original_user_message = message

    await run_agent(message)


# 채팅 입력
message = st.chat_input("Write a message for your assistant")

if message:
    if "text_placeholder" in st.session_state:
        st.session_state["text_placeholder"].empty()

    if message:
        with st.chat_message("human"):
            st.write(message)
        asyncio.run(handle_user_message(message))

# 사이드바
with st.sidebar:
    st.title("💬 Customer Support Chat")

    reset = st.button("🔄 Reset Conversation")
    if reset:
        asyncio.run(session.clear_session())
        st.session_state.current_agent = triage_agent
        if "pending_handoff" in st.session_state:
            del st.session_state.pending_handoff
        if "original_user_message" in st.session_state:
            del st.session_state.original_user_message
        st.rerun()

    st.write("---")

    # 현재 에이전트 상태
    st.write("### 🤖 Agent Status")
    if "current_agent" in st.session_state:
        agent_name = st.session_state.current_agent.name

        # 에이전트별 색상/아이콘
        agent_icons = {
            "Triage Agent": "🎯",
            "Menu Agent": "📋",
            "Order Agent": "🛒",
            "Reservation Agent": "📅",
            "Complaint Agent": "⚠️",
        }

        icon = agent_icons.get(agent_name, "🤖")
        st.success(f"{icon} **{agent_name}**")

        # Handoff 가능한 에이전트 표시
        if (
            hasattr(st.session_state.current_agent, "handoffs")
            and st.session_state.current_agent.handoffs
        ):
            with st.expander("Available Transfers"):
                for h in st.session_state.current_agent.handoffs:
                    if hasattr(h, "agent_name"):
                        transfer_icon = agent_icons.get(h.agent_name, "→")
                        st.write(f"{transfer_icon} {h.agent_name}")

    # Handoff 정보 표시
    if "pending_handoff" in st.session_state and st.session_state.pending_handoff:
        st.write("---")
        st.write("### 🔄 Handoff Info")
        info = st.session_state.pending_handoff
        st.write(f"**To:** {info.get('to_agent', 'N/A')}")
        st.write(f"**Reason:** {info.get('reason', 'N/A')}")
        st.write(f"**Issue:** {info.get('issue', 'N/A')}")

    st.write("---")

    # 디버그용 대화 기록 (토글)
    with st.expander("📜 Session History (Debug)"):
        history = asyncio.run(session.get_items())
        st.json(history)
