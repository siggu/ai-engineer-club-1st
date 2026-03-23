"""
어린이 동화책 제작 에이전트 - 루트 파이프라인

전체 흐름 (SequentialAgent):
  [사용자 입력: 테마]
       ↓
  [1] StoryProgressAgent  → Callback: "📖 스토리 작성 중..."
       ↓
  [2] StoryWriterAgent    → 5페이지 동화 생성 → state["story_output"] 저장
       ↓
  [3] ImageProgressAgent  → Callback: "🎨 5개의 삽화를 동시에 생성합니다..."
       ↓
  [4] ParallelImageAgent  → 5개 이미지를 동시 생성 (각각 Callback + Tool)
       ↓
  [5] BookAssemblerAgent  → Callback: 이미지 + 텍스트 + 페이지 번호 조합 출력
"""

from typing import Optional

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

from .sub_agents.book_assembler.agent import book_assembler_agent
from .sub_agents.parallel_image_generator.agent import parallel_image_agent
from .sub_agents.story_writer.agent import story_writer_agent

MODEL = LiteLlm(model="openai/gpt-4o")

GREETING_PATTERNS = ["안녕", "hi", "hello", "반갑", "ㅎㅇ", "헬로"]


# ──────────────────────────────────────────────
# Callbacks
# ──────────────────────────────────────────────

def make_progress_callback(message: str):
    """진행 메시지를 프런트엔드에 스트리밍하는 Callback.

    before_agent_callback 이 types.Content 를 반환하면 ADK는 LLM 호출 없이
    해당 Content 를 프런트엔드 이벤트로 바로 전송합니다.
    """

    def callback(callback_context: CallbackContext) -> types.Content:
        print(f"\n{message}\n")
        return types.Content(role="model", parts=[types.Part(text=message)])

    return callback


def validate_theme_callback(callback_context: CallbackContext) -> Optional[types.Content]:
    """입력이 인사말이거나 너무 짧으면 파이프라인 전체를 건너뜁니다.

    None 을 반환하면 파이프라인이 정상 실행됩니다.
    """
    try:
        user_text = ""
        if callback_context.user_content and callback_context.user_content.parts:
            user_text = (callback_context.user_content.parts[0].text or "").strip()
    except Exception:
        return None

    is_greeting = any(p in user_text.lower() for p in GREETING_PATTERNS)
    is_too_short = len(user_text) < 3

    if is_greeting or is_too_short:
        return types.Content(
            role="model",
            parts=[
                types.Part(
                    text=(
                        "안녕하세요! 어린이 동화책 제작 에이전트입니다. 😊\n\n"
                        "어떤 테마로 동화를 만들어 드릴까요?\n\n"
                        "예시:\n"
                        "- 용감한 아기 고양이\n"
                        "- 신비한 숲속의 토끼\n"
                        "- 하늘을 나는 코끼리"
                    )
                )
            ],
        )
    return None  # 테마 입력 → 파이프라인 실행


def after_pipeline_callback(callback_context: CallbackContext) -> None:
    print("\n✅ 동화책 완성!\n")


# ──────────────────────────────────────────────
# 진행 메시지 전용 에이전트
# before_agent_callback 이 Content 반환 → LLM 호출 없이 프런트엔드에 표시
# ──────────────────────────────────────────────

story_progress_agent = LlmAgent(
    name="StoryProgressAgent",
    model=MODEL,
    description="스토리 작성 시작을 알리는 진행 메시지 에이전트",
    instruction="",
    before_agent_callback=make_progress_callback("📖 스토리 작성 중..."),
)

image_progress_agent = LlmAgent(
    name="ImageProgressAgent",
    model=MODEL,
    description="이미지 생성 시작을 알리는 진행 메시지 에이전트",
    instruction="",
    before_agent_callback=make_progress_callback("🎨 5개의 삽화를 동시에 생성합니다..."),
)


# ──────────────────────────────────────────────
# Root Agent: SequentialAgent
# 모든 sub-agent 이벤트가 프런트엔드에 순서대로 스트리밍됩니다.
# ──────────────────────────────────────────────

root_agent = SequentialAgent(
    name="ChildrensBookMakerAgent",
    description="어린이 동화책을 만드는 에이전트",
    sub_agents=[
        story_progress_agent,   # Callback → "📖 스토리 작성 중..."
        story_writer_agent,     # LLM → 5페이지 동화 작성, state["story_output"] 저장
        image_progress_agent,   # Callback → "🎨 5개의 삽화를 동시에 생성합니다..."
        parallel_image_agent,   # ParallelAgent → 5개 이미지 동시 생성
        book_assembler_agent,   # Callback → 이미지 + 텍스트 + 페이지번호 인라인 출력
    ],
    before_agent_callback=validate_theme_callback,  # 인사/짧은 입력 → 파이프라인 스킵
    after_agent_callback=after_pipeline_callback,
)
