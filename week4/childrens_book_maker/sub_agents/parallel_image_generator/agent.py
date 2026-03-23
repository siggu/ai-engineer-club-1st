"""
ParallelAgent - 5개의 삽화를 동시에 생성합니다.

각 페이지는 SequentialAgent 로 구성됩니다:
  [PageProgressAgent_N]  → Callback: "🎨 이미지 N/5 생성 중..."
       ↓
  [PageImageAgent_N]     → Tool: generate_page_image(page_number=N)
                           state["story_output"] 에서 scene_description 읽기
                           OpenAI 이미지 생성 → artifact + state["image_data_N"] 저장

5개의 SequentialAgent 가 ParallelAgent 안에서 동시에 실행됩니다.
"""

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

from .tools import generate_page_image

MODEL = LiteLlm(model="openai/gpt-4o")


def make_page_progress_callback(page_num: int):
    """각 페이지 이미지 생성 시작을 알리는 Callback."""

    def callback(callback_context: CallbackContext) -> types.Content:
        message = f"🎨 이미지 {page_num}/5 생성 중..."
        print(f"\n{message}\n")
        return types.Content(role="model", parts=[types.Part(text=message)])

    return callback


def make_page_sequential_agent(page_number: int) -> SequentialAgent:
    """한 페이지의 [진행 표시 → 이미지 생성] SequentialAgent를 생성합니다."""

    # ① 진행 메시지 에이전트: Callback이 Content 반환 → LLM 호출 없음
    progress_agent = LlmAgent(
        name=f"PageProgressAgent_{page_number}",
        model=MODEL,
        description=f"페이지 {page_number} 이미지 생성 시작을 알리는 에이전트",
        instruction="",
        before_agent_callback=make_page_progress_callback(page_number),
    )

    # ② 이미지 생성 에이전트: generate_page_image 툴 호출
    image_agent = LlmAgent(
        name=f"PageImageAgent_{page_number}",
        model=MODEL,
        description=f"페이지 {page_number}의 삽화를 생성하는 에이전트",
        instruction=f"""당신은 어린이 동화책 삽화 생성 에이전트입니다.
페이지 {page_number}의 이미지를 생성하는 것이 당신의 유일한 역할입니다.

반드시 generate_page_image 도구를 page_number={page_number}로 즉시 호출하세요.
도구 호출 외에 다른 텍스트를 출력하지 마세요.""",
        tools=[generate_page_image],
    )

    return SequentialAgent(
        name=f"PageSequentialAgent_{page_number}",
        description=f"페이지 {page_number} 진행 표시 후 이미지 생성",
        sub_agents=[progress_agent, image_agent],
    )


# ParallelAgent: 5개 페이지를 동시에 생성
parallel_image_agent = ParallelAgent(
    name="ParallelImageAgent",
    description="5개의 페이지 삽화를 동시에 생성하는 에이전트",
    sub_agents=[make_page_sequential_agent(i) for i in range(1, 6)],
)
