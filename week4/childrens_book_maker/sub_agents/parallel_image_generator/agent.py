from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.lite_llm import LiteLlm
from google.genai import types
from .tools import generate_page_image

MODEL = LiteLlm(model="openai/gpt-4o")


def make_page_progress_callback(page_num: int):
    """before_agent_callback이 types.Content를 반환 → ADK가 frontend 이벤트로 스트리밍"""

    def callback(callback_context: CallbackContext) -> types.Content:
        message = f"🎨 이미지 {page_num}/5 생성 중..."
        print(f"\n{message}\n")
        return types.Content(
            role="model",
            parts=[types.Part(text=message)],
        )

    return callback


def make_page_sequential_agent(page_number: int) -> SequentialAgent:
    # 진행 메시지 에이전트: callback이 Content를 반환해 frontend에 표시, LLM 호출 없음
    progress_agent = LlmAgent(
        name=f"PageProgressAgent_{page_number}",
        model=MODEL,
        description=f"페이지 {page_number} 이미지 생성 시작을 알리는 에이전트",
        instruction="",
        before_agent_callback=make_page_progress_callback(page_number),
    )

    # 실제 이미지 생성 에이전트
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


parallel_image_agent = ParallelAgent(
    name="ParallelImageAgent",
    description="5개의 페이지 삽화를 동시에 생성하는 에이전트",
    sub_agents=[make_page_sequential_agent(i) for i in range(1, 6)],
)
