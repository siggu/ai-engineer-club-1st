import json
import os
import threading
import time
import uuid
import streamlit as st
import httpx

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="꼬리에 꼬리를 무는 면접",
    page_icon="🎯",
    layout="wide",
)

# ── 유저 ID (쿼리 파라미터로 브라우저에 유지) ────────────────────────
if "uid" not in st.query_params:
    st.query_params["uid"] = str(uuid.uuid4())
USER_ID: str = st.query_params["uid"]

# ── 세션 상태 초기화 ─────────────────────────────────────────────────
for key, default in {
    "stage": "setup",
    "session_id": None,
    "current_question": None,
    "history": [],
    "report": None,
    "interview_config": {},
    "free_order_page": 0,
    "fo_answers": {},  # free_order 모드 임시 답변 저장 (key: question_pool index)
    "jd_url_preview": None,
    "jd_summary": {},  # 면접 중 사이드바에 표시할 JD 요약
    "jd_raw": "",  # 추출된 JD 원문 (파싱 실패 시 fallback)
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── API 호출 헬퍼 ────────────────────────────────────────────────────


def api_get_library() -> dict[str, list[str]]:
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{API_URL}/library", params={"user_id": USER_ID})
        resp.raise_for_status()
        return resp.json()  # {"jd": [...], "resume": [...], "portfolio": [...]}
    except Exception:
        return {"jd": [], "resume": [], "portfolio": []}


def api_delete_library_file(doc_type: str, filename: str) -> None:
    with httpx.Client(timeout=5) as client:
        resp = client.delete(
            f"{API_URL}/library/{doc_type}/{filename}", params={"user_id": USER_ID}
        )
    resp.raise_for_status()


def api_get_session_status(session_id: str) -> dict:
    with httpx.Client(timeout=10) as client:
        resp = client.get(f"{API_URL}/sessions/{session_id}/status")
    resp.raise_for_status()
    return resp.json()


def api_extract_url(url: str) -> dict:
    with httpx.Client(timeout=30) as client:
        resp = client.post(f"{API_URL}/extract-url", json={"url": url})
    resp.raise_for_status()
    return resp.json()  # {"text": str, "chars": int}


def api_start_session(
    jd_file,
    resume_file,
    portfolio_file,
    interview_config: dict,
    jd_url: str | None = None,
    jd_text: str | None = None,
    jd_library: str | None = None,
    resume_library: str | None = None,
    portfolio_library: str | None = None,
) -> dict:
    files: dict = {}
    data: dict = {"interview_config": json.dumps(interview_config), "user_id": USER_ID}

    if jd_file:
        files["jd"] = (
            jd_file.name,
            jd_file.getvalue(),
            jd_file.type or "application/octet-stream",
        )
    elif jd_url:
        data["jd_url"] = jd_url
    elif jd_text:
        data["jd_text"] = jd_text
    elif jd_library:
        data["jd_library"] = jd_library

    if resume_file:
        files["resume"] = (
            resume_file.name,
            resume_file.getvalue(),
            resume_file.type or "application/octet-stream",
        )
    elif resume_library:
        data["resume_library"] = resume_library

    if portfolio_file:
        files["portfolio"] = (
            portfolio_file.name,
            portfolio_file.getvalue(),
            portfolio_file.type or "application/octet-stream",
        )
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
    "tech": ("#1d4ed8", "#dbeafe"),
    "experience": ("#15803d", "#dcfce7"),
    "pressure": ("#b91c1c", "#fee2e2"),
}
_TYPE_LABEL = {"tech": "기술", "experience": "경험", "pressure": "압박"}
_DIFF_COLOR = {
    "easy": ("#166534", "#bbf7d0"),
    "medium": ("#92400e", "#fef3c7"),
    "hard": ("#7f1d1d", "#fecaca"),
}
_DIFF_LABEL = {"easy": "쉬움", "medium": "보통", "hard": "어려움"}


def _badge(text: str, fg: str, bg: str) -> str:
    return (
        f"<span style='background:{bg};color:{fg};padding:3px 11px;"
        f"border-radius:20px;font-size:12px;font-weight:600;letter-spacing:.3px'>{text}</span>"
    )


def _render_question_card(q_dict: dict, q_num: int, total: int) -> None:
    q_type = q_dict.get("type", "tech")
    q_diff = q_dict.get("difficulty", "medium")
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

    hint = q_dict.get("hint", "")
    missing = q_dict.get("missing_point", "")
    if hint:
        missing_html = (
            f"<p style='margin:8px 0 0 0;color:#a16207;font-size:12px'>⚠️ 부족했던 점: {missing}</p>"
            if missing
            else ""
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
    _TYPE_LABEL_KO = {
        "jd": "채용공고",
        "resume": "자기소개서",
        "portfolio": "포트폴리오",
    }

    # ── 사이드바: 문서 업로드 + 면접 설정 ────────────────────────────
    with st.sidebar:
        st.markdown("## 면접 설정")

        library_files = api_get_library()

        # ── 저장된 파일 라이브러리 ────────────────────────────────────
        total_lib = sum(len(v) for v in library_files.values())
        if total_lib:
            with st.expander(f"내 파일 라이브러리 ({total_lib}개)", expanded=False):
                for doc_type, fnames in library_files.items():
                    if not fnames:
                        continue
                    st.caption(_TYPE_LABEL_KO[doc_type].upper())
                    for fname in fnames:
                        col_f, col_d = st.columns([8, 1])
                        col_f.caption(f"📄 {fname}")
                        if col_d.button("✕", key=f"del_{doc_type}_{fname}", help=f"{fname} 삭제"):
                            try:
                                api_delete_library_file(doc_type, fname)
                                st.toast(f"{fname} 삭제됨")
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))

        # ── JD 섹션 ──────────────────────────────────────────────────
        st.markdown("**📄 채용공고** `필수`")
        jd_mode = st.radio(
            "JD 입력 방식",
            options=["파일", "URL", "직접 입력", "라이브러리"],
            horizontal=True,
            label_visibility="collapsed",
        )

        jd_file = jd_url = jd_text_paste = jd_lib_jd = None

        if jd_mode == "파일":
            jd_file = st.file_uploader(
                "채용공고 파일",
                type=["pdf", "txt", "md"],
                key="up_jd",
                label_visibility="collapsed",
            )

        elif jd_mode == "URL":
            jd_url = st.text_input(
                "채용공고 URL",
                key="jd_url_input",
                placeholder="https://www.wanted.co.kr/...",
                label_visibility="collapsed",
            )
            st.caption("⚠️ React 기반 사이트(잡플래닛 등)는 추출이 불완전할 수 있습니다. 정확한 분석은 '직접 입력'을 권장합니다.")

        elif jd_mode == "직접 입력":
            jd_text_paste = st.text_area(
                "채용공고 내용 붙여넣기",
                key="jd_text_paste",
                height=180,
                placeholder="채용공고 내용을 여기에 붙여넣으세요...",
                label_visibility="collapsed",
            )
            if jd_text_paste:
                st.caption(f"{len(jd_text_paste):,}자 입력됨")

        elif jd_mode == "라이브러리":
            jd_lib_files = library_files.get("jd", [])
            if jd_lib_files:
                sel = st.selectbox(
                    "저장된 JD 선택",
                    options=[_none] + jd_lib_files,
                    key="lib_jd",
                    label_visibility="collapsed",
                )
                jd_lib_jd = None if sel == _none else sel
            else:
                st.caption("저장된 채용공고가 없습니다. 파일을 먼저 업로드해주세요.")

        st.divider()

        # ── AI 모델 선택 ──────────────────────────────────────────────
        st.markdown("**🤖 AI 모델**")
        _MODEL_OPTIONS = {
            "anthropic": [
                ("claude-sonnet-4-6", "Claude Sonnet 4.6 (권장)"),
                ("claude-haiku-4-5-20251001", "Claude Haiku 4.5 (빠름)"),
            ],
            "openai": [
                ("gpt-5.4-mini", "GPT-5.4-mini"),
                ("gpt-5.4-nano", "GPT-5.4-nano"),
            ],
        }
        col_p, col_m = st.columns(2)
        llm_provider = col_p.selectbox(
            "제공사",
            options=["anthropic", "openai"],
            format_func=lambda x: "Anthropic" if x == "anthropic" else "OpenAI",
            key="sel_llm_provider",
        )
        llm_model = col_m.selectbox(
            "모델",
            options=[m for m, _ in _MODEL_OPTIONS[llm_provider]],
            format_func=lambda x: next(
                (label for m, label in _MODEL_OPTIONS[llm_provider] if m == x), x
            ),
            key="sel_llm_model",
        )

        st.divider()

        # ── 자기소개서 / 포트폴리오 + 설정 (form 안) ──────────────────
        with st.form("upload_form"):

            def _file_slot(
                icon: str, label: str, key_up: str, key_lib: str, doc_type: str
            ):
                st.markdown(f"**{icon} {label}**")
                f = st.file_uploader(
                    label,
                    type=["pdf", "txt", "md"],
                    key=key_up,
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

            resume_file, resume_library = _file_slot(
                "📝", "자기소개서", "up_resume", "lib_resume", "resume"
            )
            portfolio_file, portfolio_library = _file_slot(
                "💼", "포트폴리오", "up_portfolio", "lib_portfolio", "portfolio"
            )

            st.divider()
            st.markdown("**⚙️ 면접 설정**")

            n_questions = st.slider("질문 수", min_value=5, max_value=20, value=10, step=1)

            _free_order = st.toggle(
                "자유 선택 모드",
                value=False,
                help="켜면 모든 질문이 한 번에 표시되고 원하는 순서로 답변할 수 있습니다.",
            )
            interview_mode = "free_order" if _free_order else "sequential"

            _simple_coaching = st.toggle(
                "즉시 채점 모드",
                value=False,
                help="켜면 힌트·심화 질문 없이 바로 다음 질문으로 넘어갑니다.",
            )
            coaching_mode = "simple" if _simple_coaching else "full"

            question_type = st.radio(
                "질문 유형",
                options=["mixed", "tech", "experience", "pressure"],
                format_func=lambda x: {"mixed": "혼합", "tech": "기술", "experience": "경험", "pressure": "압박"}[x],
                horizontal=True,
            )
            difficulty = st.radio(
                "난이도",
                options=["mixed", "easy", "medium", "hard"],
                format_func=lambda x: {"mixed": "혼합", "easy": "쉬움", "medium": "보통", "hard": "어려움"}[x],
                horizontal=True,
            )

            submitted = st.form_submit_button(
                "면접 시작하기 →",
                type="primary",
                use_container_width=True,
            )

    # ── 메인 영역 ─────────────────────────────────────────────────────
    if submitted:
        jd_lib = jd_lib_jd  # 라이브러리 모드일 때만 값이 있음
        resume_lib = None if resume_library == _none else resume_library
        portf_lib = None if portfolio_library == _none else portfolio_library

        jd_ok = bool(jd_file or jd_url or jd_text_paste or jd_lib)
        if not jd_ok:
            st.error(
                "채용공고(JD)는 필수입니다. 파일·URL·직접 입력·라이브러리 중 하나를 선택해주세요."
            )
        else:
            interview_config = {
                "interview_mode": interview_mode,
                "n_questions": n_questions,
                "coaching_mode": coaching_mode,
                "question_type": question_type,
                "difficulty": difficulty,
                "llm_provider": llm_provider,
                "llm_model": llm_model,
            }
            st.session_state.interview_config = interview_config

            _ANALYSIS_STEPS = [
                (
                    "📄",
                    "문서 읽기 및 파싱 중...",
                    "JD · 이력서 · 포트폴리오를 텍스트로 변환하고 있습니다.",
                ),
                (
                    "🔍",
                    "JD 요구사항 분석 중...",
                    "채용공고에서 핵심 기술 스택과 자격요건을 추출합니다.",
                ),
                (
                    "👤",
                    "이력서 · 포트폴리오 분석 중...",
                    "경력 사항, 프로젝트, 보유 기술을 파악합니다.",
                ),
                (
                    "🔗",
                    "기술 스택 매칭 중...",
                    "JD 요구사항과 지원자 역량의 일치 · 부족 항목을 비교합니다.",
                ),
                (
                    "🌐",
                    "최신 기술 트렌드 검색 중...",
                    "관련 기술의 최신 동향을 웹에서 보강하고 있습니다.",
                ),
                (
                    "💡",
                    "면접 질문 풀 생성 중...",
                    "분석 결과를 바탕으로 맞춤형 질문을 구성합니다.",
                ),
            ]

            result_box: dict = {}
            error_box: dict = {}

            def _run_api():
                try:
                    result_box["v"] = api_start_session(
                        jd_file,
                        resume_file,
                        portfolio_file,
                        interview_config,
                        jd_url=jd_url if not jd_file else None,
                        jd_text=jd_text_paste if not jd_file and not jd_url else None,
                        jd_library=jd_lib,
                        resume_library=resume_lib,
                        portfolio_library=portf_lib,
                    )
                except Exception as exc:
                    error_box["v"] = exc

            api_thread = threading.Thread(target=_run_api, daemon=True)
            api_thread.start()

            # 진행 상황 UI (Streamlit 네이티브 컴포넌트)
            st.markdown("#### 🤖 AI가 문서를 분석하고 있습니다")
            st.caption("보통 30~60초 소요됩니다")
            progress_bar = st.progress(0)
            step_containers = [st.empty() for _ in _ANALYSIS_STEPS]

            step_idx = 0
            while api_thread.is_alive():
                cur = step_idx % len(_ANALYSIS_STEPS)
                bar_pct = (cur + 1) / len(_ANALYSIS_STEPS)
                progress_bar.progress(bar_pct, text=f"{cur + 1} / {len(_ANALYSIS_STEPS)} 단계")

                for i, (s_icon, s_title, s_desc) in enumerate(_ANALYSIS_STEPS):
                    if i < cur:
                        step_containers[i].success(f"**{s_title}**  \n{s_desc}", icon="✅")
                    elif i == cur:
                        step_containers[i].info(f"**{s_icon} {s_title}**  \n{s_desc}", icon=None)
                    else:
                        step_containers[i].empty()

                time.sleep(7)
                step_idx += 1

            api_thread.join()
            progress_bar.empty()
            for c in step_containers:
                c.empty()

            try:
                if "v" in error_box:
                    raise error_box["v"]
                result = result_box["v"]
                st.session_state.session_id = result["session_id"]
                st.session_state.current_question = result["question"]
                st.session_state.jd_summary = result.get("jd_summary", {})
                st.session_state.jd_raw = result.get("jd_raw", "")
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
                <h1 style="font-size:36px;font-weight:800;margin:12px 0 8px 0;color:inherit">
                    꼬리에 꼬리를 무는 면접
                </h1>
                <p style="color:inherit;opacity:0.65;font-size:16px;margin:0;line-height:1.6">
                    채용공고 × 자기소개서 × 포트폴리오를 AI가 교차 분석해<br>
                    <strong style="opacity:1">당신에게 꼭 맞는 기술면접</strong>을 실시간으로 진행합니다
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 핵심 기능 카드 (2×2)
        st.markdown(
            "<p style='font-size:11px;font-weight:700;color:inherit;opacity:0.45;letter-spacing:1.5px;"
            "text-align:center;text-transform:uppercase;margin-bottom:20px'>핵심 기능</p>",
            unsafe_allow_html=True,
        )
        feat_r1c1, feat_r1c2 = st.columns(2)
        feat_r2c1, feat_r2c2 = st.columns(2)

        _FEATURES = [
            (
                feat_r1c1,
                "🔍",
                "3자 교차 분석",
                "JD · 이력서 · 포트폴리오를 동시에 분석해 지원자의 강점·약점·리스크를 정확히 파악합니다.",
                "#dbeafe",
                "#1d4ed8",
            ),
            (
                feat_r1c2,
                "🌐",
                "실시간 웹 검색 보강",
                "Tavily 검색으로 최신 기술 트렌드를 자동으로 수집해 질문의 정확도를 높입니다.",
                "#dcfce7",
                "#15803d",
            ),
            (
                feat_r2c1,
                "🎓",
                "동적 코칭 시스템",
                "답변 점수에 따라 힌트 제공 → 유사 문제 출제 → 심화 질문으로 수준을 자동 조절합니다.",
                "#fef3c7",
                "#92400e",
            ),
            (
                feat_r2c2,
                "📊",
                "세션 종합 리포트",
                "면접 종료 후 문항별 피드백, 점수 이력, 취약 카테고리를 한눈에 확인할 수 있습니다.",
                "#ede9fe",
                "#6d28d9",
            ),
        ]

        for col, icon, title, desc, bg, fg in _FEATURES:
            col.markdown(
                f"""
                <div style="background:var(--secondary-background-color);border-left:4px solid {fg};
                            border-radius:12px;padding:22px 24px;height:100%;margin-bottom:12px">
                    <div style="font-size:28px;margin-bottom:10px">{icon}</div>
                    <div style="font-size:15px;font-weight:700;color:{fg};margin-bottom:8px">{title}</div>
                    <div style="font-size:13px;color:inherit;opacity:0.75;line-height:1.6">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("<div style='margin-top:36px'></div>", unsafe_allow_html=True)

        # 사용 흐름 (3단계)
        st.markdown(
            "<p style='font-size:11px;font-weight:700;color:inherit;opacity:0.45;letter-spacing:1.5px;"
            "text-align:center;text-transform:uppercase;margin-bottom:20px'>사용 방법</p>",
            unsafe_allow_html=True,
        )
        step1, step2, step3 = st.columns(3)
        _STEPS = [
            (
                step1,
                "1",
                "문서 업로드",
                "왼쪽 사이드바에서 채용공고(필수)와 자기소개서·포트폴리오를 업로드하거나 라이브러리에서 선택하세요.",
            ),
            (
                step2,
                "2",
                "면접 설정",
                "면접 방식(순서대로/자유 선택), 질문 수, 코칭 방식, 유형, 난이도를 원하는 대로 설정하세요.",
            ),
            (
                step3,
                "3",
                "면접 시작",
                "'면접 시작하기' 버튼을 누르면 AI가 문서를 분석하고 맞춤형 질문을 생성합니다.",
            ),
        ]
        for col, num, title, desc in _STEPS:
            col.markdown(
                f"""
                <div style="text-align:center;padding:24px 20px;border:1px solid rgba(128,128,128,0.25);
                            border-radius:12px;background:var(--secondary-background-color);height:100%">
                    <div style="width:36px;height:36px;border-radius:50%;background:var(--text-color);
                                color:var(--background-color);font-size:16px;font-weight:800;line-height:36px;
                                margin:0 auto 14px auto">{num}</div>
                    <div style="font-size:15px;font-weight:700;color:inherit;margin-bottom:8px">{title}</div>
                    <div style="font-size:13px;color:inherit;opacity:0.65;line-height:1.6">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ── 2단계: 면접 진행 ─────────────────────────────────────────────────
elif st.session_state.stage == "interview":
    q = st.session_state.current_question
    history = st.session_state.history

    # ── 사이드바: JD 요약 ─────────────────────────────────────────────
    jd_summary = st.session_state.get("jd_summary", {})
    jd_raw = st.session_state.get("jd_raw", "")

    # 파싱된 섹션 중 실제 내용이 있는 것만 추림
    def _has_content(v) -> bool:
        if isinstance(v, list):
            return len(v) > 0
        if isinstance(v, dict):
            return any(v.values())
        return bool(str(v).strip())

    filled = {k: v for k, v in jd_summary.items() if _has_content(v)}

    if filled or jd_raw:
        with st.sidebar:
            st.markdown("### 📋 채용공고 요약")

            if filled:
                _SECTION_ICON = {"주요업무": "💼", "자격요건": "✅", "우대사항": "⭐"}
                for section, content in filled.items():
                    icon = _SECTION_ICON.get(section, "•")
                    with st.expander(
                        f"{icon} {section}", expanded=(section == "주요업무")
                    ):
                        if isinstance(content, list):
                            for item in content:
                                st.markdown(f"- {item}")
                        elif isinstance(content, dict):
                            for k, v in content.items():
                                st.markdown(f"**{k}**: {v}")
                        else:
                            st.markdown(str(content))

            # 파싱 내용이 없거나 일부만 있을 때 원문 제공
            if jd_raw and len(filled) < len(jd_summary):
                missing = [k for k in jd_summary if k not in filled]
                label = (
                    "원문 전체 보기"
                    if not filled
                    else f"원문 보기 (미표시: {', '.join(missing)})"
                )
                warn = jd_raw.startswith("⚠️")
                if warn:
                    st.warning(
                        "URL에서 JD 핵심 내용을 추출하지 못했습니다. '직접 입력' 탭을 권장합니다."
                    )
                with st.expander(f"📄 {label}", expanded=not filled):
                    display_text = jd_raw.split("\n\n", 1)[-1] if warn else jd_raw
                    st.text_area(
                        "채용공고 원문",
                        value=display_text,
                        height=300,
                        disabled=True,
                        label_visibility="collapsed",
                    )

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

            answer_key = f"fo_answer_{cur_q['index']}"

            # 캐러셀 네비게이션
            nav_left, nav_center, nav_right = st.columns([1, 6, 1])
            with nav_left:
                if st.button("◀", disabled=(page == 0), use_container_width=True):
                    # 현재 답변을 fo_answers에 저장한 뒤 이동
                    st.session_state.fo_answers[cur_q["index"]] = st.session_state.get(
                        answer_key, ""
                    )
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
                    # 현재 답변을 fo_answers에 저장한 뒤 이동
                    st.session_state.fo_answers[cur_q["index"]] = st.session_state.get(
                        answer_key, ""
                    )
                    st.session_state.free_order_page += 1
                    st.rerun()

            # 질문 카드
            _render_question_card(cur_q, answered_count + 1, total)

            # 답변 입력 — fo_answers에 저장된 값으로 초기화 (Streamlit이 미렌더링 widget 값 삭제하는 문제 방지)
            if answer_key not in st.session_state:
                st.session_state[answer_key] = st.session_state.fo_answers.get(
                    cur_q["index"], ""
                )
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
                            # 제출 완료된 질문의 임시 저장 답변 삭제
                            st.session_state.fo_answers.pop(cur_q["index"], None)
                            st.session_state.free_order_page = 0  # 다음 라운드 초기화

                            if result["status"] == "in_progress":
                                st.session_state.current_question = result["question"]
                                st.rerun()
                            else:
                                st.session_state.report = result["report"]
                                st.session_state.stage = "complete"
                                st.rerun()

                        except (httpx.HTTPStatusError, Exception) as e:
                            err_msg = (
                                e.response.text
                                if isinstance(e, httpx.HTTPStatusError)
                                else str(e)
                            )
                            # 에러가 나도 백엔드가 완료됐을 수 있으므로 상태를 확인한다
                            try:
                                status_data = api_get_session_status(
                                    st.session_state.session_id
                                )
                                if status_data["status"] == "complete":
                                    st.session_state.report = status_data["report"]
                                    st.session_state.stage = "complete"
                                    st.rerun()
                                else:
                                    st.session_state.current_question = status_data[
                                        "question"
                                    ]
                                    st.error(
                                        f"제출 중 오류가 발생했지만 상태를 복구했습니다: {err_msg}"
                                    )
                                    st.rerun()
                            except Exception:
                                st.error(f"오류 발생: {err_msg}")

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

                    except (httpx.HTTPStatusError, Exception) as e:
                        err_msg = (
                            e.response.text
                            if isinstance(e, httpx.HTTPStatusError)
                            else str(e)
                        )
                        try:
                            status_data = api_get_session_status(
                                st.session_state.session_id
                            )
                            if status_data["status"] == "complete":
                                st.session_state.report = status_data["report"]
                                st.session_state.stage = "complete"
                                st.rerun()
                            else:
                                st.session_state.current_question = status_data[
                                    "question"
                                ]
                                st.error(
                                    f"제출 중 오류가 발생했지만 상태를 복구했습니다: {err_msg}"
                                )
                                st.rerun()
                        except Exception:
                            st.error(f"오류 발생: {err_msg}")

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
