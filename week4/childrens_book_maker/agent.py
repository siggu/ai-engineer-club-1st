from typing import Optional
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.lite_llm import LiteLlm
from google.genai import types
from .sub_agents.story_writer.agent import story_writer_agent
from .sub_agents.parallel_image_generator.agent import parallel_image_agent
from .sub_agents.book_assembler.agent import book_assembler_agent

MODEL = LiteLlm(model="openai/gpt-4o")

GREETING_PATTERNS = ["안녕", "hi", "hello", "반갑", "ㅎㅇ", "헬로"]


def make_progress_callback(message: str):
    """before_agent_callback이 Content 반환 → ADK가 frontend 이벤트로 스트리밍 (LLM 호출 없음)."""

    def callback(callback_context: CallbackContext) -> types.Content:
        print(f"\n{message}\n")
        return types.Content(role="model", parts=[types.Part(text=message)])

    return callback


def validate_theme_callback(callback_context: CallbackContext) -> Optional[types.Content]:
    """테마가 없는 입력(인사 등)이면 Content를 반환해 파이프라인 전체를 스킵하고 안내 메시지 표시."""
    try:
        user_content = callback_context.user_content
        user_text = ""
        if user_content and user_content.parts:
            user_text = (user_content.parts[0].text or "").strip()
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
    return None  # 테마가 있으면 파이프라인 실행


def after_pipeline_callback(callback_context: CallbackContext):
    print("\n✅ 동화책 완성!\n")


# 진행 메시지 전용 에이전트 (before_callback이 Content 반환 → frontend 표시, LLM 호출 없음)
story_progress_agent = LlmAgent(
    name="StoryProgressAgent",
    model=MODEL,
    description="스토리 작성 시작을 알리는 에이전트",
    instruction="",
    before_agent_callback=make_progress_callback("📖 스토리 작성 중..."),
)

image_progress_agent = LlmAgent(
    name="ImageProgressAgent",
    model=MODEL,
    description="이미지 생성 시작을 알리는 에이전트",
    instruction="",
    before_agent_callback=make_progress_callback("🎨 5개의 삽화를 동시에 생성합니다..."),
)

# Root: SequentialAgent → 모든 sub-agent 이벤트가 frontend에 직접 스트리밍됨
root_agent = SequentialAgent(
    name="ChildrensBookMakerAgent",
    description="어린이 동화책을 만드는 에이전트",
    sub_agents=[
        story_progress_agent,  # frontend: "📖 스토리 작성 중..."
        story_writer_agent,    # 5페이지 동화 작성 → story_output 저장
        image_progress_agent,  # frontend: "🎨 5개의 삽화를 동시에 생성합니다..."
        parallel_image_agent,  # 5개 이미지 동시 생성 (각 페이지: "🎨 이미지 N/5 생성 중...")
        book_assembler_agent,  # 최종 출력: 제목 + 5페이지 텍스트 + 이미지
    ],
    before_agent_callback=validate_theme_callback,  # 인사면 파이프라인 스킵, 테마면 실행
    after_agent_callback=after_pipeline_callback,
)
