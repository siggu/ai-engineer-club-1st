from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from pydantic import BaseModel
from .prompt import PROMPT_BUILDER_DESCRIPTION, PROMPT_BUILDER_PROMPT

MODEL = LiteLlm(model="openai/gpt-4o")


class OptimizedPrompt(BaseModel):
    scene_id: int
    enhanced_prompt: str


class PromptBuilderOutput(BaseModel):
    optimized_prompts: list[OptimizedPrompt]


prompt_builder_agent = Agent(
    name="PromptBuilderAgent",
    model=MODEL,
    description=PROMPT_BUILDER_DESCRIPTION,
    instruction=PROMPT_BUILDER_PROMPT,
    output_key="prompt_builder_output",
    output_schema=PromptBuilderOutput,
)
