import sys
import os
import uuid
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.graph.graph import create_default_graph

st.set_page_config(page_title="꼬리에 꼬리를 무는 면접", layout="wide")
st.title("꼬리에 꼬리를 무는 면접")

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


FOLLOWUP_STYLE_LABELS = {
    "contradiction": "모순 지적 (방금 말한 것과 다른 상황 제시)",
    "deepdive": "심화 탐색 (더 깊이 설명 요구)",
    "counterexample": "반례 제시 (실패하는 케이스 질문)",
    "practical": "실전 적용 (실제 구현 방법 질문)",
}

PRESSURE_LABELS = {
    "low": "낮음 — 많이 부족할 때만 꼬리질문",
    "medium": "보통 — 애매한 답변에도 꼬리질문",
    "high": "높음 — 항상 꼬리질문 + 모순/빈 곳 공략",
}

# 사이드바
with st.sidebar:
    st.header("면접 정보 입력")

    jd_raw = st.text_area(
        "채용 공고 (JD) *",
        placeholder="채용 공고 내용을 붙여넣거나 URL을 입력하세요.",
        height=180,
    )
    resume_input = st.text_area(
        "이력서",
        placeholder="이력서 내용을 붙여넣거나 URL을 입력하세요. (선택)",
        height=120,
    )
    portfolio_input = st.text_area(
        "포트폴리오",
        placeholder="포트폴리오 URL 또는 내용을 입력하세요. (선택)",
        height=80,
    )

    st.divider()
    st.header("면접 설정")

    total_questions = st.slider("기본 질문 수", min_value=3, max_value=15, value=5)
    max_followup_depth = st.slider(
        "꼬리질문 최대 깊이", min_value=1, max_value=4, value=2
    )

    pressure_level = st.radio(
        "압박 강도",
        options=list(PRESSURE_LABELS.keys()),
        format_func=lambda x: PRESSURE_LABELS[x],
        index=1,
    )

    st.markdown("**꼬리질문 방식** (복수 선택)")
    selected_styles = [
        key
        for key, label in FOLLOWUP_STYLE_LABELS.items()
        if st.checkbox(label, value=key in ("deepdive", "counterexample"))
    ]

    feedback_timing = st.radio(
        "피드백 시점",
        options=["each", "final"],
        format_func=lambda x: "매 질문 후" if x == "each" else "면접 종료 후 일괄",
        index=0,
    )

    show_model_answer = st.toggle("모범 답안 공개 (학습 모드)", value=False)

    st.divider()

    start_btn = st.button("면접 시작", type="primary", use_container_width=True)

    if st.button("새 면접 시작", use_container_width=True):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.interview_started = False
        st.rerun()


# 면접 시작
if start_btn and jd_raw.strip():
    user_config_input = {
        "total_questions": total_questions,
        "max_followup_depth": max_followup_depth,
        "pressure_level": pressure_level,
        "followup_styles": selected_styles if selected_styles else ["deepdive"],
        "feedback_timing": feedback_timing,
        "show_model_answer": show_model_answer,
    }

    with st.spinner("입력 내용을 분석 중입니다..."):
        result = st.session_state.graph.invoke(  # type: ignore[arg-type]
            {
                "jd_raw": jd_raw,
                "resume_raw": resume_input if resume_input.strip() else None,
                "portfolio_raw": portfolio_input if portfolio_input.strip() else None,
                "user_config": user_config_input,
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
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("답변을 평가 중입니다..."):
                result = st.session_state.graph.invoke(  # type: ignore[arg-type]
                    {"messages": [{"role": "user", "content": user_input}]},
                    config=get_config(),
                )
            new_messages = result.get("messages", [])
            if new_messages:
                last = new_messages[-1]
                st.markdown(last.content)
                st.session_state.messages.append(last)
