from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from .prompt import BOOK_ASSEMBLER_DESCRIPTION, BOOK_ASSEMBLER_PROMPT

MODEL = LiteLlm(model="openai/gpt-4o")

book_assembler_agent = LlmAgent(
    name="BookAssemblerAgent",
    model=MODEL,
    description=BOOK_ASSEMBLER_DESCRIPTION,
    instruction=BOOK_ASSEMBLER_PROMPT,
)
