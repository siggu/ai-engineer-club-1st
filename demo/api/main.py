import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langgraph.types import Command
from pydantic import BaseModel

from api.schemas import AnswerRequest, AnswerResponse, SessionResponse
from app.graph.builder import graph

app = FastAPI(title="InterviewForge API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR  = Path("data/uploads")
LIBRARY_DIR = Path("data/library")


def _save_upload(file: Optional[UploadFile], dest: Path) -> Optional[str]:
    if file is None or not file.filename:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    path = dest.with_suffix(Path(file.filename).suffix)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return str(path)


_VALID_DOC_TYPES = {"jd", "resume", "portfolio"}


def _save_to_library(file: Optional[UploadFile], doc_type: str) -> Optional[str]:
    """업로드된 파일을 타입별 서브디렉토리에 저장한다."""
    if file is None or not file.filename:
        return None
    subdir = LIBRARY_DIR / doc_type
    subdir.mkdir(parents=True, exist_ok=True)
    dest = subdir / file.filename
    file.file.seek(0)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    file.file.seek(0)
    return str(dest)


class _ExtractUrlBody(BaseModel):
    url: str


_JD_KEYWORDS = [
    "주요업무", "담당업무", "자격요건", "자격 요건", "우대사항",
    "responsibilities", "requirements", "qualifications",
]


def _is_jd_content(text: str) -> bool:
    """추출된 텍스트가 실제 채용공고 내용인지 간단히 검증한다 (키워드 2개 이상)."""
    tl = text.lower()
    return sum(kw.lower() in tl for kw in _JD_KEYWORDS) >= 2


def _extract_json_ld_job(html: str) -> str | None:
    """JSON-LD JobPosting 스키마에서 채용공고 텍스트를 추출한다."""
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
            if not isinstance(data, dict):
                continue
            if data.get("@type") != "JobPosting":
                continue
            parts = []
            for field in ["title", "description", "qualifications",
                          "responsibilities", "skills", "experienceRequirements"]:
                if val := data.get(field):
                    parts.append(str(val))
            if parts:
                return "\n\n".join(parts)
        except Exception:
            pass
    return None


def _extract_next_data(html: str) -> str | None:
    """Next.js __NEXT_DATA__ JSON에서 긴 문자열을 재귀적으로 수집한다."""
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if not tag or not tag.string:
        return None
    try:
        data = json.loads(tag.string)
    except Exception:
        return None

    def _collect(obj: object, min_len: int = 15) -> list[str]:
        if isinstance(obj, str):
            return [obj] if len(obj) >= min_len else []
        if isinstance(obj, dict):
            return [s for v in obj.values() for s in _collect(v, min_len)]
        if isinstance(obj, list):
            return [s for item in obj for s in _collect(item, min_len)]
        return []

    chunks = _collect(data)
    seen: set[str] = set()
    unique = [c for c in chunks if not (c in seen or seen.add(c))]  # type: ignore[func-returns-value]
    text = "\n".join(unique)
    return text if len(text) >= 200 else None


def _extract_text_from_url(url: str) -> str:
    """URL에서 텍스트를 추출해 반환한다.
    시도 순서: Tavily extract → JSON-LD → __NEXT_DATA__ → BS4 main 영역 → BS4 전체
    각 단계에서 실제 JD 내용인지 검증하고, 가장 적합한 결과를 선택한다.
    """
    import os

    best: str = ""
    best_is_jd: bool = False  # JD 키워드 2개 이상 포함 여부

    def _update(candidate: str | None) -> None:
        nonlocal best, best_is_jd
        if not candidate:
            return
        is_jd = _is_jd_content(candidate)
        # JD 품질 우선, 같은 품질이면 길이 우선
        if (is_jd and not best_is_jd) or (is_jd == best_is_jd and len(candidate) > len(best)):
            best = candidate
            best_is_jd = is_jd

    # 1차: Tavily extract (JS 렌더링 SPA 지원)
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key:
        try:
            from tavily import TavilyClient
            tc = TavilyClient(api_key=tavily_key)
            response = tc.extract(urls=[url])
            results = response.get("results", [])
            if results:
                _update(results[0].get("raw_content", "").strip())
        except Exception:
            pass

    # Tavily로 이미 JD 내용 확보 시 조기 반환
    if best_is_jd and len(best) >= 300:
        return best

    # 2차: httpx로 HTML 직접 fetch
    raw_html: str | None = None
    try:
        with httpx.Client(
            timeout=20, follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "ko-KR,ko;q=0.9",
            },
        ) as client:
            resp = client.get(url)
        resp.raise_for_status()
        raw_html = resp.text
    except httpx.HTTPStatusError as e:
        if not best:
            raise HTTPException(400, f"URL 접근 실패 ({e.response.status_code}): {url}")
    except Exception as e:
        if not best:
            raise HTTPException(400, f"URL 요청 오류: {e}")

    if raw_html:
        # 2-1: JSON-LD JobPosting 스키마 (가장 정확)
        _update(_extract_json_ld_job(raw_html))

        # 2-2: Next.js __NEXT_DATA__ (SPA 내장 데이터)
        _update(_extract_next_data(raw_html))

        # 2-3: BeautifulSoup — main/article 영역 우선
        soup = BeautifulSoup(raw_html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside",
                         "button", "form", "iframe"]):
            tag.decompose()

        main_area = soup.find("main") or soup.find("article")
        if main_area:
            candidate = re.sub(r"\n{3,}", "\n\n", main_area.get_text("\n", strip=True)).strip()
            _update(candidate)

        # 2-4: 페이지 전체 텍스트 (최후 폴백)
        candidate = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True)).strip()
        _update(candidate)

    if not best or len(best) < 50:
        raise HTTPException(
            400,
            "URL에서 텍스트를 추출할 수 없습니다. "
            "JS 전용 렌더링 페이지(React/Next.js 등)는 서버에서 접근이 제한됩니다.\n\n"
            "해결 방법: '직접 입력' 탭에 채용공고 내용을 붙여넣어 주세요.",
        )

    if not best_is_jd:
        # 내용은 추출됐지만 JD 키워드가 없음 → 경고와 함께 반환
        best = (
            "⚠️ 채용공고 핵심 내용을 추출하지 못했을 수 있습니다. "
            "'직접 입력' 탭에 내용을 붙여넣으면 더 정확합니다.\n\n"
            + best
        )

    return best


def _fetch_url_text(url: str, dest: Path) -> str:
    """URL에서 텍스트를 추출해 .txt 파일로 저장한다."""
    text = _extract_text_from_url(url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    path = dest.with_suffix(".txt")
    path.write_text(text, encoding="utf-8")
    return str(path)


def _get_interrupt(config: dict) -> Optional[dict]:
    snapshot = graph.get_state(config)
    if snapshot.tasks and snapshot.tasks[0].interrupts:
        return snapshot.tasks[0].interrupts[0].value
    return None


# ── 라이브러리 엔드포인트 ─────────────────────────────────────────────

@app.get("/library")
def list_library(user_id: str = ""):
    """유저별 타입별 라이브러리 파일 목록을 반환한다."""
    result: dict[str, list[str]] = {"jd": [], "resume": [], "portfolio": []}
    if not user_id:
        return result
    for doc_type in result:
        subdir = LIBRARY_DIR / user_id / doc_type
        if subdir.exists():
            result[doc_type] = sorted(f.name for f in subdir.iterdir() if f.is_file())
    return result


@app.delete("/library/{doc_type}/{filename}")
def delete_library_file(doc_type: str, filename: str, user_id: str = ""):
    """유저별 라이브러리 파일을 삭제한다."""
    if doc_type not in _VALID_DOC_TYPES:
        raise HTTPException(400, "잘못된 문서 유형입니다.")
    if not user_id:
        raise HTTPException(400, "user_id가 필요합니다.")
    path = LIBRARY_DIR / user_id / doc_type / filename
    if not path.exists():
        raise HTTPException(404, "파일을 찾을 수 없습니다.")
    path.unlink()
    return {"deleted": filename}


# ── URL 미리보기 엔드포인트 ──────────────────────────────────────────

@app.post("/extract-url")
def extract_url_preview(body: _ExtractUrlBody):
    """URL에서 텍스트를 추출해 미리보기용으로 반환한다 (세션 시작 없음)."""
    text = _extract_text_from_url(body.url)
    return {"text": text, "chars": len(text)}


# ── 세션 엔드포인트 ──────────────────────────────────────────────────

@app.post("/sessions", response_model=SessionResponse)
def start_session(
    jd: Optional[UploadFile] = File(None),
    resume: Optional[UploadFile] = File(None),
    portfolio: Optional[UploadFile] = File(None),
    jd_url: Optional[str] = Form(None),            # URL로 JD 제공
    jd_text: Optional[str] = Form(None),           # 직접 텍스트 입력
    jd_library: Optional[str] = Form(None),
    resume_library: Optional[str] = Form(None),
    portfolio_library: Optional[str] = Form(None),
    interview_config: str = Form("{}"),
    user_id: Optional[str] = Form(None),
):
    session_id = str(uuid.uuid4())
    base = UPLOAD_DIR / session_id

    def _user_lib(doc_type: str) -> Path:
        return LIBRARY_DIR / (user_id or "_global") / doc_type

    def _resolve(
        upload: Optional[UploadFile],
        url: Optional[str],
        raw_text: Optional[str],
        library_name: Optional[str],
        doc_type: str,
        dest: Path,
    ) -> Optional[str]:
        """우선순위: 파일 업로드 > URL > 직접 텍스트 > 라이브러리"""
        if upload and upload.filename:
            lib_dest = _user_lib(doc_type) / upload.filename
            lib_dest.parent.mkdir(parents=True, exist_ok=True)
            lib_dest.write_bytes(upload.file.read())
            upload.file.seek(0)
            return _save_upload(upload, dest)
        if url and url.strip():
            return _fetch_url_text(url.strip(), dest)
        if raw_text and raw_text.strip():
            dest.parent.mkdir(parents=True, exist_ok=True)
            path = dest.with_suffix(".txt")
            path.write_text(raw_text.strip(), encoding="utf-8")
            return str(path)
        if library_name:
            lib_path = _user_lib(doc_type) / library_name
            if lib_path.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                target = dest.with_suffix(lib_path.suffix)
                shutil.copy(lib_path, target)
                return str(target)
        return None

    selected_files = {
        "jd":        _resolve(jd,        jd_url,  jd_text, jd_library,        "jd",        base / "jd"),
        "resume":    _resolve(resume,    None,    None,    resume_library,    "resume",    base / "resume"),
        "portfolio": _resolve(portfolio, None,    None,    portfolio_library, "portfolio", base / "portfolio"),
    }

    if not selected_files.get("jd"):
        raise HTTPException(400, "채용공고(JD)는 필수입니다.")

    try:
        config_dict = json.loads(interview_config)
    except json.JSONDecodeError:
        config_dict = {}

    config = {"configurable": {"thread_id": session_id}}
    try:
        graph.invoke(
            {
                "selected_files":   selected_files,
                "interview_config": config_dict,
            },
            config=config,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"그래프 실행 오류: {type(e).__name__}: {e}")

    question = _get_interrupt(config)
    if question is None:
        raise HTTPException(500, "면접 시작에 실패했습니다.")

    state_values = graph.get_state(config).values
    jd_summary = state_values.get("jd_parsed", {})
    jd_raw     = state_values.get("jd_raw", "")
    return {
        "session_id": session_id,
        "status": "in_progress",
        "question": question,
        "jd_summary": jd_summary,
        "jd_raw": jd_raw,
    }


@app.post("/sessions/{session_id}/answer", response_model=AnswerResponse)
def submit_answer(session_id: str, body: AnswerRequest):
    config = {"configurable": {"thread_id": session_id}}

    snapshot = graph.get_state(config)
    if not snapshot.values:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")

    if body.selected_index is not None:
        resume_value = {"selected_index": body.selected_index, "answer": body.answer}
    else:
        resume_value = body.answer

    try:
        graph.invoke(Command(resume=resume_value), config=config)
    except Exception:
        # graph.invoke가 예외를 던져도 그래프 상태를 확인해 완료 여부를 판단한다
        pass

    question = _get_interrupt(config)
    if question is not None:
        return {"status": "in_progress", "question": question}

    state = graph.get_state(config).values
    if not state:
        raise HTTPException(500, "세션 상태를 확인할 수 없습니다.")

    score_history = state.get("score_history", [])
    avg = sum(score_history) / len(score_history) if score_history else 0.0

    return {
        "status": "complete",
        "report": {
            "session_history": state.get("session_history", []),
            "score_history":   score_history,
            "weak_categories": list(set(state.get("weak_categories", []))),
            "average_score":   round(avg, 1),
        },
    }


@app.get("/sessions/{session_id}/status")
def get_session_status(session_id: str):
    """세션의 현재 상태를 조회한다 (invoke 없이 읽기 전용)."""
    config = {"configurable": {"thread_id": session_id}}
    snapshot = graph.get_state(config)
    if not snapshot.values:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")

    question = _get_interrupt(config)
    if question is not None:
        return {"status": "in_progress", "question": question}

    state = snapshot.values
    score_history = state.get("score_history", [])
    avg = sum(score_history) / len(score_history) if score_history else 0.0
    return {
        "status": "complete",
        "report": {
            "session_history": state.get("session_history", []),
            "score_history":   score_history,
            "weak_categories": list(set(state.get("weak_categories", []))),
            "average_score":   round(avg, 1),
        },
    }


@app.get("/health")
def health():
    return {"status": "ok"}
