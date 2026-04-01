SIMILAR_Q_PROMPT = """당신은 기술면접 전문 출제자입니다.
지원자가 아래 질문에 부분적으로 답했습니다. 같은 키워드·난이도로 다른 각도의 질문을 1개 생성하세요. 마크다운 코드블록 없이 JSON만 반환하세요.

[원래 질문]
{question}

[관련 키워드]
{related_keyword}

[난이도]
{difficulty}

[지원자 답변]
{answer}

[점수]
{score} / 10.0

[지시]
- 원래 질문과 동일한 related_keyword, difficulty를 유지하세요.
- 지원자가 답변하지 못한 부분을 다른 각도로 검증하는 질문을 만드세요.
- 원래 질문과 거의 동일한 질문은 피하세요.

[출력 형식]
{{
  "id": 0,
  "type": "{q_type}",
  "difficulty": "{difficulty}",
  "question": "새 질문 내용",
  "intent": "이 질문의 평가 의도",
  "related_keyword": "{related_keyword}"
}}"""
