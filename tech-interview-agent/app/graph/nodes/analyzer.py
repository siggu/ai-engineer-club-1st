from app.llm import get_llm, DEFAULT_MODEL
from app.graph.state import AppState, AnalysisResult
from app.prompts.analyzer import ANALYZER_PROMPT


def analyzer(state: AppState) -> dict:
    """
    JD / 이력서 / 포트폴리오를 교차 분석하여 압박 면접 전략 재료를 생성하는 노드.
    user_config.model에 지정된 LLM을 사용합니다.
    """
    model_id = (state.get("user_config") or {}).get("model", DEFAULT_MODEL)
    structured_llm = get_llm(model_id).with_structured_output(AnalysisResult)

    prompt = ANALYZER_PROMPT.format(
        jd_text=state.get("jd_text") or "(없음)",
        resume_text=state.get("resume_text") or "(없음)",
        portfolio_text=state.get("portfolio_text") or "(없음)",
    )

    result: AnalysisResult = structured_llm.invoke(prompt)  # type: ignore[assignment]

    return {"analysis_result": result}
