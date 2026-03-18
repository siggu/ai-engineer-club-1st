from google.adk.agents import Agent
from google.adk.tools import AgentTool
from google.adk.models.lite_llm import LiteLlm
from .prompt_builder.agent import prompt_builder_agent
from .image_builder.agent import image_builder_agent
from .prompt import IMAGE_GENERATOR_DESCRIPTION, IMAGE_GENERATOR_PROMPT

MODEL = LiteLlm(model="openai/gpt-4o")

image_generator_agent = Agent(
    name="ImageGeneratorAgent",
    model=MODEL,
    description=IMAGE_GENERATOR_DESCRIPTION,
    instruction=IMAGE_GENERATOR_PROMPT,
    tools=[
        AgentTool(agent=prompt_builder_agent),
        AgentTool(agent=image_builder_agent),
    ],
)
