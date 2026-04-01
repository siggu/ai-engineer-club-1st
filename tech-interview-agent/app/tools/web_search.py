from langchain_tavily import TavilySearch

web_search_tool = TavilySearch(
    max_results=3,
    description="웹 서치 기능이 필요할 때 사용합니다.",
)
