from langchain.chat_models import init_chat_model

# 선택 가능한 모델 목록 { model_id: 표시 이름 }
AVAILABLE_MODELS: dict[str, str] = {
    "openai:gpt-5.4-mini":                 "GPT-5.4 Mini (OpenAI)",
    "openai:gpt-5.4":                      "GPT-5.4 (OpenAI)",
    "anthropic:claude-haiku-4-5-20251001": "Claude Haiku 4.5 (Anthropic)",
    "anthropic:claude-sonnet-4-6":         "Claude Sonnet 4.6 (Anthropic)",
}

DEFAULT_MODEL = "openai:gpt-5.4-mini"


def get_llm(model_id: str = DEFAULT_MODEL):
    """model_id로 LLM 인스턴스를 반환합니다. (예: 'openai:gpt-4o-mini')"""
    return init_chat_model(model_id)
