import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
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

UPLOAD_DIR = Path("data/uploads")


def _save_upload(file: Optional[UploadFile], dest: Path) -> Optional[str]:
    if file is None or not file.filename:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    path = dest.with_suffix(Path(file.filename).suffix)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return str(path)


def _get_interrupt(config: dict) -> Optional[dict]:
    snapshot = graph.get_state(config)
    if snapshot.tasks and snapshot.tasks[0].interrupts:
        return snapshot.tasks[0].interrupts[0].value
    return None


@app.post("/sessions", response_model=SessionResponse)
def start_session(
    jd: Optional[UploadFile] = File(None),
    resume: Optional[UploadFile] = File(None),
    portfolio: Optional[UploadFile] = File(None),
):
    session_id = str(uuid.uuid4())
    base = UPLOAD_DIR / session_id

    selected_files = {
        "jd":        _save_upload(jd,        base / "jd"),
        "resume":    _save_upload(resume,    base / "resume"),
        "portfolio": _save_upload(portfolio, base / "portfolio"),
    }

    if not any(selected_files.values()):
        raise HTTPException(400, "파일을 하나 이상 업로드해주세요.")

    config = {"configurable": {"thread_id": session_id}}
    graph.invoke({"selected_files": selected_files}, config=config)

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

    graph.invoke(Command(resume=body.answer), config=config)

    question = _get_interrupt(config)
    if question is not None:
        return {"status": "in_progress", "question": question}

    # 면접 완료
    state = graph.get_state(config).values
    score_history = state.get("score_history", [])
    avg = sum(score_history) / len(score_history) if score_history else 0.0

    return {
        "status": "complete",
        "report": {
            "session_history":  state.get("session_history", []),
            "score_history":    score_history,
            "weak_categories":  list(set(state.get("weak_categories", []))),
            "average_score":    round(avg, 1),
        },
    }


@app.get("/health")
def health():
    return {"status": "ok"}
