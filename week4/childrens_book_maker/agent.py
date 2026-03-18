from google.adk.agents import Agent
from google.adk.tools import AgentTool
from google.adk.models.lite_llm import LiteLlm
from .sub_agents.content_planner.agent import content_planner_agent
from .sub_agents.asset_generator.image_generator.agent import image_generator_agent
from .prompt import CHILDREN_BOOK_MAKER_DESCRIPTION, CHILDREN_BOOK_MAKER_PROMPT

MODEL = LiteLlm(model="openai/gpt-4o")

children_book_maker_agent = Agent(
    name="ChildrensBookMakerAgent",
    model=MODEL,
    description=CHILDREN_BOOK_MAKER_DESCRIPTION,
    instruction=CHILDREN_BOOK_MAKER_PROMPT,
    tools=[
        AgentTool(agent=content_planner_agent),
        AgentTool(agent=image_generator_agent),
    ],
)

root_agent = children_book_maker_agent
