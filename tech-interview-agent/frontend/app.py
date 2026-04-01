import sys
import os
import uuid
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.graph.graph import create_default_graph

st.set_page_config(page_title="AI 기술 면접 에이전트", layout="wide")
st.title("AI 기술 면접 에이전트")


# 세션 초기화
if "graph" not in st.session_state:
    st.session_state.graph = create_default_graph()

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "interview_started" not in st.session_state:
    st.session_state.interview_started = False


def get_config():
    return {
        "configurable": {"thread_id": st.session_state.thread_id},
        "recursion_limit": 10,
    }


# 사이드바: 입력 정보
with st.sidebar:
    st.header("면접 정보 입력")

    jd_raw = st.text_area(
        "채용 공고 (JD)",
        placeholder="채용 공고 내용을 붙여넣거나 URL을 입력하세요.",
        height=200,
    )

    resume_input = st.text_area(
        "이력서",
        placeholder="이력서 내용을 붙여넣거나 URL을 입력하세요. (선택)",
        height=150,
    )

    portfolio_input = st.text_area(
        "포트폴리오",
        placeholder="포트폴리오 URL 또는 내용을 입력하세요. (선택)",
        height=100,
    )

    start_btn = st.button("면접 시작", type="primary", use_container_width=True)

    if st.button("새 면접 시작", use_container_width=True):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.interview_started = False
        st.rerun()


# 면접 시작
if start_btn and jd_raw.strip():
    with st.spinner("입력 내용을 분석 중입니다..."):
        result = st.session_state.graph.invoke(
            {
                "jd_raw": jd_raw,
                "resume_raw": resume_input if resume_input.strip() else None,
                "portfolio_raw": portfolio_input if portfolio_input.strip() else None,
            },
            config=get_config(),
        )
    st.session_state.interview_started = True
    st.session_state.messages = []
    for msg in result.get("messages", []):
        st.session_state.messages.append(msg)
    st.rerun()

elif start_btn:
    st.sidebar.error("채용 공고(JD)를 입력해주세요.")


# 채팅 화면
if not st.session_state.interview_started:
    st.info("왼쪽 사이드바에 채용 공고를 입력하고 '면접 시작' 버튼을 눌러주세요.")
else:
    for msg in st.session_state.messages:
        role = "assistant" if msg.type == "ai" else "user"
        with st.chat_message(role):
            st.markdown(msg.content)

    user_input = st.chat_input("답변을 입력하세요...")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("답변을 평가 중입니다..."):
                result = st.session_state.graph.invoke(
                    {"messages": [{"role": "user", "content": user_input}]},
                    config=get_config(),
                )
            new_messages = result.get("messages", [])
            if new_messages:
                last = new_messages[-1]
                st.markdown(last.content)
                st.session_state.messages.append(last)
