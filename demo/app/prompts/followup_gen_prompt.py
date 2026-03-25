FOLLOWUP_GEN_PROMPT = """당신은 기술면접 전문 출제자입니다.
지원자가 아래 질문에 훌륭하게 답했습니다. 답변 내용을 바탕으로 더 깊이 파고드는 심화 꼬리 질문을 1개 생성하세요. 마크다운 코드블록 없이 JSON만 반환하세요.

[원래 질문]
{question}

[관련 키워드]
{related_keyword}

[지원자 답변]
{answer}

[점수]
{score} / 10.0

[지시]
- 지원자가 언급한 내용 중 더 깊이 탐구할 수 있는 부분을 찾으세요.
- 난이도는 원래 질문보다 한 단계 높게 설정하세요 (easy→medium, medium→hard, hard→hard).
- 단순 암기가 아닌 실무 판단력을 검증하는 질문을 만드세요.

[출력 형식]
{{
  "id": 0,
  "type": "{q_type}",
  "difficulty": "{difficulty}",
  "question": "심화 꼬리 질문 내용",
  "intent": "이 질문의 평가 의도",
  "related_keyword": "{related_keyword}"
}}"""
