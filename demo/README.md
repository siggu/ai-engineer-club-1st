# InterviewForge

LangGraph 기반 기술면접 코칭 에이전트.
채용공고(JD) × 자기소개서 × 포트폴리오를 교차 분석하여 맞춤형 면접 질문을 생성하고, 답변 수준에 따라 힌트·유사 질문·심화 꼬리 질문으로 동적 코칭합니다.

---

## 주요 기능

- **문서 분석**: JD / 자기소개서 / 포트폴리오를 병렬로 파싱 후 교차 분석
- **웹 검색 연동**: 회사 기술 블로그·면접 후기를 자율적으로 검색해 분석에 반영
- **맞춤형 질문 생성**: tech / experience / pressure 3유형, 취약 영역 가중 출제
- **동적 코칭**: 점수에 따라 힌트 제공 → 유사 질문 → 심화 꼬리 질문으로 분기
- **세션 영속성**: SQLite에 세션 저장, 다음 면접에 이전 취약 영역 자동 반영
- **결과 리포트**: 전체 Q&A / 모범답안 / 피드백 / 점수 일람 출력

---

## 아키텍처

```
START
  │
  ▼
read_files          ← 파일 읽기 (LLM 없음)
  │
  └── dispatch_parsing() [Send API — 병렬]
        ├──► parse_doc (jd)
        ├──► parse_doc (resume)
        └──► parse_doc (portfolio)
                 │
                 ▼
           merge_parsed
                 │
                 ▼
analyzer ◄───────────────────────────┐
  │    (web_search_tool 자율 호출)    │
  └── route_analyzer()               │
        ├── search → tool_node ──────┘
        └── done   → questioner

questioner          ← 질문 Pool 생성 (자가 평가 내장)
  │
  ▼
interviewer ⏸       ← interrupt() — 사용자 답변 대기
  │
  └── route_by_score()
        ├── score < 5  → hint_provider   → interviewer
        ├── score 5~7  → similar_q       → interviewer
        └── score ≥ 8  → followup_gen    → interviewer
                 │
                 ▼
             evaluator  ← 채점 + 피드백 + 모범답안
                 │
           check_completion()
                 ├── continue → interviewer
                 └── done     → report_gen → END
```

---

## 노드 설명

| 노드 | 역할 |
|---|---|
| `read_files` | 파일 경로를 받아 원본 텍스트만 읽음 (LLM 호출 없음) |
| `parse_doc` | 문서 1개를 타입별 프롬프트로 구조화 파싱. Send API로 3개 동시 실행 |
| `merge_parsed` | 병렬 파싱 결과 수집 (State에 자동 누적) |
| `analyzer` | JD × 자소서 × 포트폴리오 교차 분석. 필요 시 `web_search_tool` 자율 호출 |
| `tool_node` | Tavily 웹 검색 실행 후 결과를 `analyzer`로 반환 |
| `questioner` | skill_match / jd_keywords / weak_categories 기반 질문 Pool 생성. 프롬프트 내 자가 평가 포함 |
| `interviewer` | 질문 출제 후 `interrupt()`로 사용자 답변 수집 |
| `hint_provider` | 점수 < 5일 때 힌트를 제공하고 같은 질문 재출제 |
| `similar_q` | 점수 5~7일 때 유사 난이도의 다른 질문 생성 |
| `followup_gen` | 점수 ≥ 8일 때 심화 꼬리 질문 생성 |
| `evaluator` | 0~10점 채점 + 피드백 + 모범답안 생성, session_history 누적 |
| `report_gen` | 전체 Q&A / 점수 / 모범답안 / 피드백 총정리 출력 |

---

## 파일 구조

```
demo/
├── app/
│   ├── parsers/
│   │   └── file_parser.py          # PDF / 텍스트 파일 읽기
│   ├── prompts/
│   │   ├── input_parser_prompt.py  # 문서 파싱 프롬프트 (JD / 자소서 / 포트폴리오)
│   │   ├── analyzer_prompt.py      # 교차 분석 + 웹 검색 반영
│   │   ├── questioner_prompt.py    # 질문 생성 + 자가 평가
│   │   ├── evaluator_prompt.py     # 채점 + 피드백 + 모범답안
│   │   ├── hint_provider_prompt.py # 힌트 생성
│   │   ├── similar_q_prompt.py     # 유사 질문 생성
│   │   └── followup_gen_prompt.py  # 심화 꼬리 질문 생성
│   └── tools/
│       └── web_search_tool.py      # Tavily 웹 검색
├── data/
│   └── sessions.db                 # 세션 이력 (SqliteSaver)
├── main.ipynb                      # 전체 구현 (노드 / 엣지 / 실행)
└── pyproject.toml
```

---

## 시작하기

### 1. 의존성 설치

```bash
cd demo
uv sync
```

### 2. 환경 변수 설정

```bash
cp .env.example .env
```

`.env` 파일에 아래 키를 입력합니다.

```env
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...
```

### 3. 실행

`main.ipynb`를 열고 셀을 순서대로 실행합니다.

```python
# 분석할 파일 경로 지정
selected_files = {
    "jd":        "data/jd.txt",        # 채용공고 (필수)
    "resume":    "data/resume.txt",    # 자기소개서 (선택)
    "portfolio": "data/portfolio.pdf", # 포트폴리오 (선택)
}

result = graph.invoke(
    {"selected_files": selected_files},
    config={"configurable": {"thread_id": "session-1"}},
)
```

### 4. 답변 제출

`interviewer` 노드에서 질문이 출력되면 아래 셀에 답변을 작성하고 실행합니다.

```python
MY_ANSWER = "여기에 답변을 입력하세요"

graph.invoke(
    Command(resume=MY_ANSWER),
    config={"configurable": {"thread_id": "session-1"}},
)
```

### 5. 2회차 면접 (이전 취약 영역 반영)

```python
prev_state     = graph.get_state({"configurable": {"thread_id": "session-1"}})
weak_from_prev = prev_state.values.get("weak_categories", [])

graph.invoke(
    {"selected_files": selected_files, "weak_categories": weak_from_prev},
    config={"configurable": {"thread_id": "session-2"}},
)
```

---

## 기술 스택

| 레이어 | 기술 |
|---|---|
| AI / Agent | LangGraph, Claude API (`claude-sonnet-4-5`), LangChain |
| 웹 검색 | Tavily (`TavilySearchResults`) |
| 세션 영속성 | `SqliteSaver` (`langgraph-checkpoint-sqlite`) |
| 문서 파싱 | `pdfplumber` |
| 병렬 실행 | LangGraph `Send` API (Map-Reduce 패턴) |
| Human-in-the-loop | `interrupt()` + `Command(resume=...)` |
