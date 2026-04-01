from dotenv import load_dotenv
from app.graph.graph import create_default_graph

load_dotenv()

graph = create_default_graph()
config = {"configurable": {"thread_id": "test-1"}, "recursion_limit": 10}

result = graph.invoke(
    {
        "jd_raw": """
    [주요업무] LLM 기반 AI 서비스 개발
    [자격요건] Python 3년 이상, FastAPI 경험
    [우대사항] LangGraph 경험, Claude API 활용 경험
    """,
        "resume_raw": "저는 LangGraph와 Claude API를 활용한 챗봇을 개발했습니다...",
        "portfolio_raw": None,
    },
    config=config,
)

print("jd_text:", result["jd_text"][:100])
print("has_resume:", result["has_resume"])
print("has_portfolio:", result["has_portfolio"])
