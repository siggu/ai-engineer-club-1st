from dotenv import load_dotenv
from langchain_community.tools.tavily_search import TavilySearchResults

load_dotenv()

web_search_tool = TavilySearchResults(
    max_results=3,
    description=(
        "회사 기술 블로그, 면접 후기, 최신 기술 트렌드를 검색합니다. "
        "JD에 회사명이 있을 때 실제 기술 스택을 파악하거나, "
        "최신 LLM/RAG 관련 면접 경향을 조사할 때 사용하세요."
    ),
)
