import json
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langgraph.types import Command

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


def _get_interrupt(config: dict) -> Optional[dict]:
    snapshot = graph.get_state(config)
    if snapshot.tasks and snapshot.tasks[0].interrupts:
        return snapshot.tasks[0].interrupts[0].value
    return None


# ── 라이브러리 엔드포인트 ─────────────────────────────────────────────

@app.get("/library")
def list_library():
    """타입별 라이브러리 파일 목록을 반환한다."""
    result: dict[str, list[str]] = {"jd": [], "resume": [], "portfolio": []}
    for doc_type in result:
        subdir = LIBRARY_DIR / doc_type
        if subdir.exists():
            result[doc_type] = sorted(f.name for f in subdir.iterdir() if f.is_file())
    return result


@app.delete("/library/{doc_type}/{filename}")
def delete_library_file(doc_type: str, filename: str):
    """라이브러리 파일을 삭제한다."""
    if doc_type not in _VALID_DOC_TYPES:
        raise HTTPException(400, "잘못된 문서 유형입니다.")
    path = LIBRARY_DIR / doc_type / filename
    if not path.exists():
        raise HTTPException(404, "파일을 찾을 수 없습니다.")
    path.unlink()
    return {"deleted": filename}


# ── 세션 엔드포인트 ──────────────────────────────────────────────────

@app.post("/sessions", response_model=SessionResponse)
def start_session(
    jd: Optional[UploadFile] = File(None),
    resume: Optional[UploadFile] = File(None),
    portfolio: Optional[UploadFile] = File(None),
    jd_library: Optional[str] = Form(None),        # 라이브러리 파일명
    resume_library: Optional[str] = Form(None),
    portfolio_library: Optional[str] = Form(None),
    interview_config: str = Form("{}"),
):
    session_id = str(uuid.uuid4())
    base = UPLOAD_DIR / session_id

    def _resolve(upload: Optional[UploadFile], library_name: Optional[str], doc_type: str, dest: Path) -> Optional[str]:
        """업로드 파일 우선, 없으면 타입별 라이브러리 파일 사용. 업로드 시 라이브러리에도 저장."""
        if upload and upload.filename:
            _save_to_library(upload, doc_type)
            return _save_upload(upload, dest)
        if library_name:
            lib_path = LIBRARY_DIR / doc_type / library_name
            if lib_path.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                target = dest.with_suffix(lib_path.suffix)
                shutil.copy(lib_path, target)
                return str(target)
        return None

    selected_files = {
        "jd":        _resolve(jd,        jd_library,        "jd",        base / "jd"),
        "resume":    _resolve(resume,    resume_library,    "resume",    base / "resume"),
        "portfolio": _resolve(portfolio, portfolio_library, "portfolio", base / "portfolio"),
    }

    if not selected_files.get("jd"):
        raise HTTPException(400, "채용공고(JD)는 필수입니다.")

    try:
        config_dict = json.loads(interview_config)
    except json.JSONDecodeError:
        config_dict = {}

    config = {"configurable": {"thread_id": session_id}}
    graph.invoke(
        {
            "selected_files":   selected_files,
            "interview_config": config_dict,
        },
        config=config,
    )

    question = _get_interrupt(config)
    if question is None:
        raise HTTPException(500, "면접 시작에 실패했습니다.")

    return {"session_id": session_id, "status": "in_progress", "question": question}


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

    graph.invoke(Command(resume=resume_value), config=config)

    question = _get_interrupt(config)
    if question is not None:
        return {"status": "in_progress", "question": question}

    state = graph.get_state(config).values
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
