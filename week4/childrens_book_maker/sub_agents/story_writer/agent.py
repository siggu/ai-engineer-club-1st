from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from .prompt import STORY_WRITER_DESCRIPTION, STORY_WRITER_PROMPT

MODEL = LiteLlm(model="openai/gpt-4o")

story_writer_agent = LlmAgent(
    name="StoryWriterAgent",
    model=MODEL,
    description=STORY_WRITER_DESCRIPTION,
    instruction=STORY_WRITER_PROMPT,
    output_key="story_output",
)
