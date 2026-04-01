import pdfplumber
import requests
from bs4 import BeautifulSoup
from io import BytesIO

from app.graph.state import AppState


def extract_text(raw: str | bytes | None) -> str:
    if not raw:
        return ""
    try:
        if isinstance(raw, bytes):
            with pdfplumber.open(BytesIO(raw)) as pdf:
                text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            if not text.strip():
                raise ValueError("PDF에서 텍스트를 추출할 수 없습니다 (스캔본일 수 있음)")
            return text.strip()

        if raw.startswith("http"):
            resp = requests.get(raw, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            return soup.get_text(separator="\n").strip()

        return raw.strip()

    except Exception as e:
        print(f"[input_parser] 텍스트 추출 실패: {e}")
        return ""


def input_parser(state: AppState):
    jd_text = extract_text(state["jd_raw"])
    resume_text = extract_text(state["resume_raw"]) if state["resume_raw"] else ""
    portfolio_text = extract_text(state["portfolio_raw"]) if state["portfolio_raw"] else ""

    return {
        "jd_text": jd_text,
        "resume_text": resume_text,
        "portfolio_text": portfolio_text,
        "has_resume": bool(resume_text),
        "has_portfolio": bool(portfolio_text),
        "messages": [],
        "session_history": [],
        "answered_count": 0,
        "weak_categories": [],
    }
