import os
import streamlit as st
import httpx

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="기술면접 도우미 에이전트",
    page_icon="🎯",
    layout="wide",
)

# ── 세션 상태 초기화 ─────────────────────────────────────────────────
for key, default in {
    "stage": "setup",
    "session_id": None,
    "current_question": None,
    "history": [],
    "report": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── API 호출 헬퍼 ────────────────────────────────────────────────────


def api_start_session(jd_file, resume_file, portfolio_file) -> dict:
    files = {}
    if jd_file:
        files["jd"] = (
            jd_file.name,
            jd_file.getvalue(),
            jd_file.type or "application/octet-stream",
        )
    if resume_file:
        files["resume"] = (
            resume_file.name,
            resume_file.getvalue(),
            resume_file.type or "application/octet-stream",
        )
    if portfolio_file:
        files["portfolio"] = (
            portfolio_file.name,
            portfolio_file.getvalue(),
            portfolio_file.type or "application/octet-stream",
        )

    with httpx.Client(timeout=120) as client:
        resp = client.post(f"{API_URL}/sessions", files=files)
    resp.raise_for_status()
    return resp.json()


def api_submit_answer(session_id: str, answer: str) -> dict:
    with httpx.Client(timeout=120) as client:
        resp = client.post(
            f"{API_URL}/sessions/{session_id}/answer",
            json={"answer": answer},
        )
    resp.raise_for_status()
    return resp.json()


# ── 1단계: 파일 업로드 ───────────────────────────────────────────────
if st.session_state.stage == "setup":
    st.title("🎯 기술면접 도우미 에이전트")
    st.markdown(
        "채용공고 × 자기소개서 × 포트폴리오를 교차 분석해 **맞춤형 기술면접**을 진행합니다."
    )
    st.divider()

    with st.form("upload_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            jd_file = st.file_uploader(
                "📄 채용공고 (JD) **필수**",
                type=["pdf", "txt", "md"],
                help="지원할 회사의 채용공고 파일을 업로드하세요.",
            )
        with col2:
            resume_file = st.file_uploader(
                "📝 자기소개서 (선택)",
                type=["pdf", "txt", "md"],
            )
        with col3:
            portfolio_file = st.file_uploader(
                "💼 포트폴리오 (선택)",
                type=["pdf", "txt", "md"],
            )

        submitted = st.form_submit_button(
            "면접 시작하기 →",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not jd_file:
            st.error("채용공고(JD)는 필수입니다.")
        else:
            with st.spinner("문서를 분석하고 있습니다... (30~60초 소요)"):
                try:
                    result = api_start_session(jd_file, resume_file, portfolio_file)
                    st.session_state.session_id = result["session_id"]
                    st.session_state.current_question = result["question"]
                    st.session_state.stage = "interview"
                    st.rerun()
                except httpx.HTTPStatusError as e:
                    st.error(f"서버 오류: {e.response.text}")
                except Exception as e:
                    st.error(f"오류 발생: {e}")


# ── 2단계: 면접 진행 ─────────────────────────────────────────────────
elif st.session_state.stage == "interview":
    q = st.session_state.current_question
    history = st.session_state.history

    q_num = q.get("question_number", 1)
    total = q.get("total_questions", 10)

    # 헤더
    col_title, col_exit = st.columns([8, 1])
    with col_title:
        st.title("🎤 기술면접 진행 중")
    with col_exit:
        if st.button("종료", type="secondary"):
            for key in ["stage", "session_id", "current_question", "history", "report"]:
                st.session_state.pop(key, None)
            st.rerun()

    # 진행 상황
    st.progress(q_num / total, text=f"**Q{q_num} / {total}**")
    st.markdown(
        f"<span style='background:#1e3a5f;padding:4px 10px;border-radius:12px;font-size:13px'>"
        f"**{q.get('type', '').upper()}** &nbsp;|&nbsp; {q.get('difficulty', '')}</span>",
        unsafe_allow_html=True,
    )
    st.markdown(f"### {q.get('question', '')}")

    # 힌트 (재출제 시)
    if q.get("hint"):
        st.info(f"💡 **힌트:** {q['hint']}")

    st.divider()

    # 답변 입력
    with st.form("answer_form", clear_on_submit=True):
        answer = st.text_area(
            "답변을 입력하세요",
            height=220,
            placeholder="구체적인 경험과 기술적 근거를 포함해 답변해 주세요...",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button(
            "답변 제출 →",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not answer.strip():
            st.warning("답변을 입력해주세요.")
        else:
            with st.spinner("채점 중..."):
                try:
                    result = api_submit_answer(
                        st.session_state.session_id, answer.strip()
                    )

                    st.session_state.history.append(
                        {
                            "q_number": q_num,
                            "type": q.get("type", ""),
                            "difficulty": q.get("difficulty", ""),
                            "question": q.get("question", ""),
                            "answer": answer.strip(),
                        }
                    )

                    if result["status"] == "in_progress":
                        st.session_state.current_question = result["question"]
                        st.rerun()
                    else:
                        st.session_state.report = result["report"]
                        st.session_state.stage = "complete"
                        st.rerun()

                except httpx.HTTPStatusError as e:
                    st.error(f"서버 오류: {e.response.text}")
                except Exception as e:
                    st.error(f"오류 발생: {e}")

    # 이전 답변 목록
    if history:
        with st.expander(f"이전 답변 보기 ({len(history)}개)", expanded=False):
            for h in reversed(history):
                st.markdown(
                    f"**Q{h['q_number']}** `{h['type']} / {h['difficulty']}`  \n"
                    f"> {h['question']}"
                )
                st.caption(
                    f"내 답변: {h['answer'][:120]}{'...' if len(h['answer']) > 120 else ''}"
                )
                st.divider()


# ── 3단계: 결과 리포트 ───────────────────────────────────────────────
elif st.session_state.stage == "complete":
    report = st.session_state.report
    session_history = report.get("session_history", [])
    avg_score = report.get("average_score", 0.0)
    weak_categories = report.get("weak_categories", [])

    st.title("📊 면접 결과 리포트")

    # 요약 지표
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("평균 점수", f"{avg_score:.1f} / 10.0")
    with col2:
        st.metric("총 문항 수", len(session_history))
    with col3:
        st.metric("종합 평가", "✅ 합격권" if avg_score >= 7 else "📚 보완 필요")

    if weak_categories:
        st.warning(f"**취약 영역:** {', '.join(weak_categories)}")

    st.divider()

    # 문항별 상세 결과
    for record in session_history:
        score = record.get("score", 0)
        score_bar = "█" * int(score) + "░" * (10 - int(score))
        label = (
            f"Q{record['q_number']} "
            f"[{record['type']} / {record['difficulty']}]  "
            f"{score:.1f}점  {score_bar}"
        )
        with st.expander(label):
            st.markdown(f"**❓ 질문**  \n{record['question']}")
            st.divider()
            st.markdown(f"**💬 내 답변**  \n{record['answer']}")
            st.divider()
            st.markdown(f"**📋 피드백**  \n{record['feedback']}")
            st.success(f"**✅ 모범답안**  \n{record['model_answer']}")

    st.divider()

    if st.button("새 면접 시작하기", type="primary", use_container_width=True):
        for key in ["stage", "session_id", "current_question", "history", "report"]:
            st.session_state.pop(key, None)
        st.rerun()
