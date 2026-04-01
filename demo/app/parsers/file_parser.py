import json
import re
import logging
from pathlib import Path

import pdfplumber

logging.getLogger("pdfplumber").setLevel(logging.ERROR)
logging.getLogger("pdfminer").setLevel(logging.ERROR)


def read_file(path: str | None) -> str:
    if path is None:
        return ""
    p = Path(path)
    if not p.exists():
        return ""
    if p.suffix == ".pdf":
        with pdfplumber.open(p) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages).strip()
    return p.read_text(encoding="utf-8").strip()


def extract_json(text: str) -> dict:
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1)
    return json.loads(text.strip())
