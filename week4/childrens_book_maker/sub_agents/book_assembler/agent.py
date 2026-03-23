"""
BookAssemblerAgent - 합성된 동화책 페이지를 순서대로 출력합니다.

tools.py 의 compose_book_page() 가 이미지·텍스트·페이지번호를
하나의 JPEG 로 합성했으므로, 여기서는 state["image_data_N"] 를
inline_data 로 출력하기만 하면 됩니다.

구조 (SequentialAgent):
  BookTitleAgent        → "# 제목"
  BookPageAgent_1 ~ 5   → 합성 페이지 이미지 1장씩
  BookCompletionAgent   → "✨ 동화책이 완성되었습니다!"
"""

import base64
import json
from typing import Optional

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

MODEL = LiteLlm(model="openai/gpt-4o")


def _parse_story(state) -> Optional[dict]:
    raw = state.get("story_output")
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None


# ── 제목 ──────────────────────────────────────────────────────

def _title_callback(callback_context: CallbackContext) -> types.Content:
    story = _parse_story(callback_context.state)
    title = story.get("title", "동화책") if story else "동화책"
    return types.Content(role="model", parts=[types.Part(text=f"# {title}\n\n")])


# ── 페이지 (합성 이미지 1장) ──────────────────────────────────

def make_page_callback(page_num: int):
    """tools.py 가 합성한 페이지 이미지를 inline_data 로 반환합니다."""

    def callback(callback_context: CallbackContext) -> types.Content:
        image_b64 = callback_context.state.get(f"image_data_{page_num}")

        if not image_b64:
            # 이미지가 없으면 텍스트로 대체
            story = _parse_story(callback_context.state)
            pages = story.get("pages", []) if story else []
            page  = next((p for p in pages if p.get("page_number") == page_num), {})
            return types.Content(
                role="model",
                parts=[types.Part(text=f"{page.get('text','')}\n\n{page_num}\n\n---\n\n")],
            )

        image_bytes = base64.b64decode(image_b64)
        return types.Content(
            role="model",
            parts=[
                types.Part(
                    inline_data=types.Blob(mime_type="image/jpeg", data=image_bytes)
                )
            ],
        )

    return callback


# ── 완료 ──────────────────────────────────────────────────────

def _completion_callback(callback_context: CallbackContext) -> types.Content:
    return types.Content(
        role="model",
        parts=[types.Part(text="✨ 동화책이 완성되었습니다!")],
    )


# ── 헬퍼 ──────────────────────────────────────────────────────

def _cb_agent(name: str, fn) -> LlmAgent:
    return LlmAgent(name=name, model=MODEL, description=name,
                    instruction="", before_agent_callback=fn)


# ── BookAssemblerAgent ────────────────────────────────────────

book_assembler_agent = SequentialAgent(
    name="BookAssemblerAgent",
    description="합성된 동화책 페이지를 순서대로 출력하는 에이전트",
    sub_agents=[
        _cb_agent("BookTitleAgent",      _title_callback),
        _cb_agent("BookPageAgent_1",     make_page_callback(1)),
        _cb_agent("BookPageAgent_2",     make_page_callback(2)),
        _cb_agent("BookPageAgent_3",     make_page_callback(3)),
        _cb_agent("BookPageAgent_4",     make_page_callback(4)),
        _cb_agent("BookPageAgent_5",     make_page_callback(5)),
        _cb_agent("BookCompletionAgent", _completion_callback),
    ],
)
