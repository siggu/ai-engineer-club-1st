import json
import os
import threading
import time
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
    "interview_config": {},
    "free_order_page": 0,  # free_order 모드 캐러셀 현재 페이지
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── API 호출 헬퍼 ────────────────────────────────────────────────────


def api_get_library() -> dict[str, list[str]]:
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{API_URL}/library")
        resp.raise_for_status()
        return resp.json()  # {"jd": [...], "resume": [...], "portfolio": [...]}
    except Exception:
        return {"jd": [], "resume": [], "portfolio": []}


def api_delete_library_file(doc_type: str, filename: str) -> None:
    with httpx.Client(timeout=5) as client:
        resp = client.delete(f"{API_URL}/library/{doc_type}/{filename}")
    resp.raise_for_status()


def api_start_session(
    jd_file,
    resume_file,
    portfolio_file,
    interview_config: dict,
    jd_library: str | None = None,
    resume_library: str | None = None,
    portfolio_library: str | None = None,
) -> dict:
    files: dict = {}
    data: dict  = {"interview_config": json.dumps(interview_config)}

    if jd_file:
        files["jd"] = (jd_file.name, jd_file.getvalue(), jd_file.type or "application/octet-stream")
    elif jd_library:
        data["jd_library"] = jd_library

    if resume_file:
        files["resume"] = (resume_file.name, resume_file.getvalue(), resume_file.type or "application/octet-stream")
    elif resume_library:
        data["resume_library"] = resume_library

    if portfolio_file:
        files["portfolio"] = (portfolio_file.name, portfolio_file.getvalue(), portfolio_file.type or "application/octet-stream")
    elif portfolio_library:
        data["portfolio_library"] = portfolio_library

    with httpx.Client(timeout=120) as client:
        resp = client.post(f"{API_URL}/sessions", files=files, data=data)
    resp.raise_for_status()
    return resp.json()


def api_submit_answer(
    session_id: str,
    answer: str,
    selected_index: int | None = None,
) -> dict:
    body: dict = {"answer": answer}
    if selected_index is not None:
        body["selected_index"] = selected_index

    with httpx.Client(timeout=120) as client:
        resp = client.post(
            f"{API_URL}/sessions/{session_id}/answer",
            json=body,
        )
    resp.raise_for_status()
    return resp.json()


# ── 질문 카드 렌더러 ─────────────────────────────────────────────────

_TYPE_COLOR = {
    "tech":       ("#1d4ed8", "#dbeafe"),
    "experience": ("#15803d", "#dcfce7"),
    "pressure":   ("#b91c1c", "#fee2e2"),
}
_TYPE_LABEL = {"tech": "기술", "experience": "경험", "pressure": "압박"}
_DIFF_COLOR = {"easy": ("#166534", "#bbf7d0"), "medium": ("#92400e", "#fef3c7"), "hard": ("#7f1d1d", "#fecaca")}
_DIFF_LABEL = {"easy": "쉬움", "medium": "보통", "hard": "어려움"}


def _badge(text: str, fg: str, bg: str) -> str:
    return (
        f"<span style='background:{bg};color:{fg};padding:3px 11px;"
        f"border-radius:20px;font-size:12px;font-weight:600;letter-spacing:.3px'>{text}</span>"
    )


def _render_question_card(q_dict: dict, q_num: int, total: int) -> None:
    q_type   = q_dict.get("type", "tech")
    q_diff   = q_dict.get("difficulty", "medium")
    question = q_dict.get("question", "")
    is_retry = q_dict.get("is_retry", False)

    type_fg, type_bg = _TYPE_COLOR.get(q_type) or ("#374151", "#f3f4f6")
    diff_fg, diff_bg = _DIFF_COLOR.get(q_diff) or ("#374151", "#f3f4f6")
    type_label = _TYPE_LABEL.get(q_type) or q_type.upper()
    diff_label = _DIFF_LABEL.get(q_diff) or q_diff

    retry_html = _badge("🔁 재도전", "#7c3aed", "#ede9fe") if is_retry else ""
    badges = (
        _badge(type_label, type_fg, type_bg)
        + "&nbsp;"
        + _badge(diff_label, diff_fg, diff_bg)
        + ("&nbsp;" + retry_html if retry_html else "")
    )

    st.markdown(
        f"""
        <div style="
            border:1px solid #e5e7eb;
            border-radius:12px;
            padding:22px 26px;
            margin:12px 0 8px 0;
            background:linear-gradient(135deg,#f9fafb 0%,#f3f4f6 100%);
        ">
            <div style="display:flex;align-items:center;gap:6px;margin-bottom:14px">
                <span style="font-size:12px;color:#9ca3af;font-weight:500">Q{q_num}&nbsp;/&nbsp;{total}</span>
                <span style="color:#d1d5db;margin:0 4px">|</span>
                {badges}
            </div>
            <p style="font-size:17px;font-weight:600;line-height:1.7;margin:0;color:#111827">
                {question}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    hint    = q_dict.get("hint", "")
    missing = q_dict.get("missing_point", "")
    if hint:
        missing_html = (
            f"<p style='margin:8px 0 0 0;color:#a16207;font-size:12px'>⚠️ 부족했던 점: {missing}</p>"
            if missing else ""
        )
        st.markdown(
            f"""
            <div style="
                border-left:4px solid #f59e0b;
                background:#fffbeb;
                border-radius:0 8px 8px 0;
                padding:14px 18px;
                margin:4px 0 12px 0;
            ">
                <p style="margin:0 0 4px 0;font-weight:700;color:#92400e;font-size:13px">💡 힌트</p>
                <p style="margin:0;color:#78350f;font-size:14px;line-height:1.6">{hint}</p>
                {missing_html}
            </div>
            """,
            unsafe_allow_html=True,
        )


# ── 1단계: 파일 업로드 + 설정 ────────────────────────────────────────
if st.session_state.stage == "setup":

    _none = "— 선택 안 함 —"
    _TYPE_LABEL_KO = {"jd": "채용공고", "resume": "자기소개서", "portfolio": "포트폴리오"}

    # ── 사이드바: 문서 업로드 + 면접 설정 ────────────────────────────
    with st.sidebar:
        st.markdown("## 🎯 면접 설정")

        library_files = api_get_library()
        total_lib = sum(len(v) for v in library_files.values())
        if total_lib:
            with st.expander(f"📁 저장된 파일 ({total_lib}개)", expanded=False):
                for doc_type, fnames in library_files.items():
                    if not fnames:
                        continue
                    st.markdown(
                        f"<p style='font-size:11px;font-weight:700;color:#6b7280;"
                        f"text-transform:uppercase;letter-spacing:.5px;margin:8px 0 4px 0'>"
                        f"{_TYPE_LABEL_KO[doc_type]}</p>",
                        unsafe_allow_html=True,
                    )
                    for fname in fnames:
                        col_f, col_d = st.columns([9, 1])
                        col_f.caption(f"📄 {fname}")
                        if col_d.button("🗑", key=f"del_{doc_type}_{fname}", help=f"{fname} 삭제"):
                            try:
                                api_delete_library_file(doc_type, fname)
                                st.toast(f"{fname} 삭제됨", icon="🗑")
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))

        with st.form("upload_form"):
            st.markdown("**📂 문서 업로드**")

            def _file_slot(icon: str, label: str, key_up: str, key_lib: str,
                           doc_type: str, required: bool = False):
                req = " \\*" if required else ""
                st.markdown(
                    f"<p style='font-size:13px;font-weight:600;margin:10px 0 4px 0'>"
                    f"{icon} {label}{req}</p>",
                    unsafe_allow_html=True,
                )
                f = st.file_uploader(
                    label, type=["pdf", "txt", "md"], key=key_up,
                    label_visibility="collapsed",
                )
                type_files = library_files.get(doc_type, [])
                lib = st.selectbox(
                    "라이브러리에서 선택",
                    options=[_none] + type_files,
                    key=key_lib,
                    disabled=bool(f),
                    label_visibility="collapsed" if f else "visible",
                )
                return f, lib

            jd_file,        jd_library        = _file_slot("📄", "채용공고 (JD)", "up_jd",        "lib_jd",        "jd",        required=True)
            resume_file,    resume_library    = _file_slot("📝", "자기소개서",     "up_resume",    "lib_resume",    "resume")
            portfolio_file, portfolio_library = _file_slot("💼", "포트폴리오",     "up_portfolio", "lib_portfolio", "portfolio")

            st.divider()
            st.markdown("**⚙️ 면접 설정**")

            interview_mode = st.selectbox(
                "면접 방식",
                options=["sequential", "free_order"],
                format_func=lambda x: "순서대로" if x == "sequential" else "자유 선택",
                help="자유 선택: 남은 질문 목록에서 직접 골라 답변합니다.",
            )
            coaching_mode = st.selectbox(
                "코칭 방식",
                options=["full", "simple"],
                format_func=lambda x: "힌트·심화 코칭" if x == "full" else "즉시 채점",
                help="full: 점수에 따라 힌트·유사문제·심화질문을 제공합니다.",
            )
            n_questions = st.slider("질문 수", min_value=5, max_value=20, value=10, step=1)
            question_type = st.selectbox(
                "질문 유형",
                options=["mixed", "tech", "experience", "pressure"],
                format_func=lambda x: {"mixed": "혼합", "tech": "기술", "experience": "경험", "pressure": "압박"}[x],
            )
            difficulty = st.selectbox(
                "난이도",
                options=["mixed", "easy", "medium", "hard"],
                format_func=lambda x: {"mixed": "혼합", "easy": "쉬움", "medium": "보통", "hard": "어려움"}[x],
            )

            submitted = st.form_submit_button(
                "면접 시작하기 →", type="primary", use_container_width=True,
            )

    # ── 메인 영역 ─────────────────────────────────────────────────────
    if submitted:
        jd_lib      = None if jd_library      == _none else jd_library
        resume_lib  = None if resume_library  == _none else resume_library
        portf_lib   = None if portfolio_library == _none else portfolio_library

        jd_ok = bool(jd_file or jd_lib)
        if not jd_ok:
            st.error("채용공고(JD)는 필수입니다. 새로 업로드하거나 라이브러리에서 선택해주세요.")
        else:
            interview_config = {
                "interview_mode": interview_mode,
                "n_questions": n_questions,
                "coaching_mode": coaching_mode,
                "question_type": question_type,
                "difficulty": difficulty,
            }
            st.session_state.interview_config = interview_config

            _ANALYSIS_STEPS = [
                ("📄", "문서 읽기 및 파싱 중...",       "JD · 이력서 · 포트폴리오를 텍스트로 변환하고 있습니다."),
                ("🔍", "JD 요구사항 분석 중...",         "채용공고에서 핵심 기술 스택과 자격요건을 추출합니다."),
                ("👤", "이력서 · 포트폴리오 분석 중...", "경력 사항, 프로젝트, 보유 기술을 파악합니다."),
                ("🔗", "기술 스택 매칭 중...",           "JD 요구사항과 지원자 역량의 일치 · 부족 항목을 비교합니다."),
                ("🌐", "최신 기술 트렌드 검색 중...",    "관련 기술의 최신 동향을 웹에서 보강하고 있습니다."),
                ("💡", "면접 질문 풀 생성 중...",        "분석 결과를 바탕으로 맞춤형 질문을 구성합니다."),
            ]

            result_box: dict = {}
            error_box:  dict = {}

            def _run_api():
                try:
                    result_box["v"] = api_start_session(
                        jd_file, resume_file, portfolio_file, interview_config,
                        jd_library=jd_lib,
                        resume_library=resume_lib,
                        portfolio_library=portf_lib,
                    )
                except Exception as exc:
                    error_box["v"] = exc

            api_thread = threading.Thread(target=_run_api, daemon=True)
            api_thread.start()

            progress_ph = st.empty()
            step_idx = 0
            while api_thread.is_alive():
                icon, title, desc = _ANALYSIS_STEPS[step_idx % len(_ANALYSIS_STEPS)]
                pct = (step_idx % len(_ANALYSIS_STEPS) + 1) / len(_ANALYSIS_STEPS)
                with progress_ph.container():
                    st.markdown(
                        f"""
                        <div style="padding:20px 24px;background:#1e2130;border-radius:12px;
                                    border-left:4px solid #4f8ef7;margin-bottom:8px;">
                          <div style="font-size:1.4rem;font-weight:700;margin-bottom:4px;">
                            {icon} {title}
                          </div>
                          <div style="color:#9aa3b8;font-size:0.9rem;">{desc}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.progress(pct)
                    st.caption(f"단계 {step_idx % len(_ANALYSIS_STEPS) + 1} / {len(_ANALYSIS_STEPS)}  ·  잠시만 기다려 주세요...")
                time.sleep(7)
                step_idx += 1

            api_thread.join()
            progress_ph.empty()

            try:
                if "v" in error_box:
                    raise error_box["v"]
                result = result_box["v"]
                st.session_state.session_id = result["session_id"]
                st.session_state.current_question = result["question"]
                st.session_state.stage = "interview"
                st.rerun()
            except httpx.HTTPStatusError as e:
                st.error(f"서버 오류: {e.response.text}")
            except Exception as e:
                st.error(f"오류 발생: {e}")

    else:
        # ── 랜딩 페이지: 기능 소개 ────────────────────────────────────

        # 히어로 헤더
        st.markdown(
            """
            <div style="text-align:center;padding:56px 0 40px 0">
                <p style="font-size:56px;margin:0">🎯</p>
                <h1 style="font-size:36px;font-weight:800;margin:12px 0 8px 0;color:#111827">
                    기술면접 도우미 에이전트
                </h1>
                <p style="color:#6b7280;font-size:16px;margin:0;line-height:1.6">
                    채용공고 × 자기소개서 × 포트폴리오를 AI가 교차 분석해<br>
                    <strong>당신에게 꼭 맞는 기술면접</strong>을 실시간으로 진행합니다
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 핵심 기능 카드 (2×2)
        st.markdown(
            "<p style='font-size:11px;font-weight:700;color:#9ca3af;letter-spacing:1.5px;"
            "text-align:center;text-transform:uppercase;margin-bottom:20px'>핵심 기능</p>",
            unsafe_allow_html=True,
        )
        feat_r1c1, feat_r1c2 = st.columns(2)
        feat_r2c1, feat_r2c2 = st.columns(2)

        _FEATURES = [
            (feat_r1c1, "🔍", "3자 교차 분석",
             "JD · 이력서 · 포트폴리오를 동시에 분석해 지원자의 강점·약점·리스크를 정확히 파악합니다.",
             "#dbeafe", "#1d4ed8"),
            (feat_r1c2, "🌐", "실시간 웹 검색 보강",
             "Tavily 검색으로 최신 기술 트렌드를 자동으로 수집해 질문의 정확도를 높입니다.",
             "#dcfce7", "#15803d"),
            (feat_r2c1, "🎓", "동적 코칭 시스템",
             "답변 점수에 따라 힌트 제공 → 유사 문제 출제 → 심화 질문으로 수준을 자동 조절합니다.",
             "#fef3c7", "#92400e"),
            (feat_r2c2, "📊", "세션 종합 리포트",
             "면접 종료 후 문항별 피드백, 점수 이력, 취약 카테고리를 한눈에 확인할 수 있습니다.",
             "#ede9fe", "#6d28d9"),
        ]

        for col, icon, title, desc, bg, fg in _FEATURES:
            col.markdown(
                f"""
                <div style="background:{bg};border-radius:12px;padding:22px 24px;height:100%;margin-bottom:12px">
                    <div style="font-size:28px;margin-bottom:10px">{icon}</div>
                    <div style="font-size:15px;font-weight:700;color:{fg};margin-bottom:8px">{title}</div>
                    <div style="font-size:13px;color:#374151;line-height:1.6">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("<div style='margin-top:36px'></div>", unsafe_allow_html=True)

        # 사용 흐름 (3단계)
        st.markdown(
            "<p style='font-size:11px;font-weight:700;color:#9ca3af;letter-spacing:1.5px;"
            "text-align:center;text-transform:uppercase;margin-bottom:20px'>사용 방법</p>",
            unsafe_allow_html=True,
        )
        step1, step2, step3 = st.columns(3)
        _STEPS = [
            (step1, "1", "문서 업로드", "왼쪽 사이드바에서 채용공고(필수)와 자기소개서·포트폴리오를 업로드하거나 라이브러리에서 선택하세요."),
            (step2, "2", "면접 설정",   "면접 방식(순서대로/자유 선택), 질문 수, 코칭 방식, 유형, 난이도를 원하는 대로 설정하세요."),
            (step3, "3", "면접 시작",   "'면접 시작하기' 버튼을 누르면 AI가 문서를 분석하고 맞춤형 질문을 생성합니다."),
        ]
        for col, num, title, desc in _STEPS:
            col.markdown(
                f"""
                <div style="text-align:center;padding:24px 20px;border:1px solid #e5e7eb;
                            border-radius:12px;background:#f9fafb;height:100%">
                    <div style="width:36px;height:36px;border-radius:50%;background:#111827;
                                color:#fff;font-size:16px;font-weight:800;line-height:36px;
                                margin:0 auto 14px auto">{num}</div>
                    <div style="font-size:15px;font-weight:700;color:#111827;margin-bottom:8px">{title}</div>
                    <div style="font-size:13px;color:#6b7280;line-height:1.6">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ── 2단계: 면접 진행 ─────────────────────────────────────────────────
elif st.session_state.stage == "interview":
    q = st.session_state.current_question
    history = st.session_state.history

    # 헤더
    col_title, col_exit = st.columns([8, 1])
    with col_title:
        st.title("🎤 기술면접 진행 중")
    with col_exit:
        if st.button("종료", type="secondary"):
            for key in [
                "stage",
                "session_id",
                "current_question",
                "history",
                "report",
                "interview_config",
            ]:
                st.session_state.pop(key, None)
            st.rerun()

    # ── free_order 모드 ──────────────────────────────────────────────
    if q.get("mode") == "free_order":
        answered_count = q.get("answered_count", 0)
        total = q.get("total_questions", 10)
        questions = q.get("questions", [])

        st.progress(
            answered_count / max(total, 1),
            text=f"**{answered_count} / {total} 완료**",
        )

        if not questions:
            st.info("모든 질문에 답변했습니다.")
        else:
            # 페이지 인덱스 범위 보정
            page = min(st.session_state.free_order_page, len(questions) - 1)
            page = max(page, 0)
            st.session_state.free_order_page = page

            cur_q = questions[page]

            # 캐러셀 네비게이션
            nav_left, nav_center, nav_right = st.columns([1, 6, 1])
            with nav_left:
                if st.button("◀", disabled=(page == 0), use_container_width=True):
                    st.session_state.free_order_page -= 1
                    st.rerun()
            with nav_center:
                st.markdown(
                    f"<p style='text-align:center;color:#6b7280;font-size:13px;margin:6px 0'>"
                    f"질문 {page + 1} / {len(questions)}</p>",
                    unsafe_allow_html=True,
                )
            with nav_right:
                if st.button(
                    "▶", disabled=(page == len(questions) - 1), use_container_width=True
                ):
                    st.session_state.free_order_page += 1
                    st.rerun()

            # 질문 카드
            _render_question_card(cur_q, answered_count + 1, total)

            # 답변 입력 — key에 question_pool 인덱스를 사용해 페이지 이동 시 입력이 보존됨
            answer_key = f"fo_answer_{cur_q['index']}"
            st.text_area(
                "답변을 입력하세요",
                height=200,
                placeholder="구체적인 경험과 기술적 근거를 포함해 답변해 주세요...",
                label_visibility="collapsed",
                key=answer_key,
            )

            if st.button("답변 제출 →", type="primary", use_container_width=True):
                answer_val = st.session_state.get(answer_key, "").strip()
                if not answer_val:
                    st.warning("답변을 입력해주세요.")
                else:
                    with st.spinner("채점 중..."):
                        try:
                            result = api_submit_answer(
                                st.session_state.session_id,
                                answer_val,
                                selected_index=cur_q["index"],
                            )

                            st.session_state.history.append(
                                {
                                    "q_number": answered_count + 1,
                                    "type": cur_q.get("type", ""),
                                    "difficulty": cur_q.get("difficulty", ""),
                                    "question": cur_q.get("question", ""),
                                    "answer": answer_val,
                                }
                            )
                            st.session_state.free_order_page = 0  # 다음 라운드 초기화

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

    # ── sequential 모드 ──────────────────────────────────────────────
    else:
        q_num = q.get("question_number", 1)
        total = q.get("total_questions", 10)

        st.progress(q_num / total, text=f"**Q{q_num} / {total}**")

        # 질문 카드
        _render_question_card(q, q_num, total)

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

    # 이전 답변 목록 (공통)
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
        for key in [
            "stage",
            "session_id",
            "current_question",
            "history",
            "report",
            "interview_config",
        ]:
            st.session_state.pop(key, None)
        st.rerun()
