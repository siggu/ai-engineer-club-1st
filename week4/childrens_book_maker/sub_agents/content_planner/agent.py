from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from .prompt import (
    CONTENT_PLANNER_PROMPT,
    CONTENT_PLANNER_DESCRIPTION,
)

MODEL = LiteLlm(model="openai/gpt-4o")

content_planner_agent = Agent(
    name="ContentPlannerAgent",
    model=MODEL,
    description=CONTENT_PLANNER_DESCRIPTION,
    instruction=CONTENT_PLANNER_PROMPT,
    output_key="content_planner_output",
)
