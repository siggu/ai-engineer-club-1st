import json
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt

from app.parsers.file_parser import read_file, extract_json
from app.prompts.input_parser_prompt import (
    JD_PARSE_PROMPT,
    RESUME_PARSE_PROMPT,
    PORTFOLIO_PARSE_PROMPT,
)
from app.prompts.analyzer_prompt import ANALYZER_PROMPT
from app.prompts.questioner_prompt import QUESTIONER_PROMPT
from app.prompts.evaluator_prompt import EVALUATOR_PROMPT
from app.prompts.hint_provider_prompt import HINT_PROVIDER_PROMPT
from app.prompts.similar_q_prompt import SIMILAR_Q_PROMPT
from app.prompts.followup_gen_prompt import FOLLOWUP_GEN_PROMPT
from app.tools.web_search_tool import web_search_tool
from .state import State

load_dotenv()

llm            = ChatAnthropic(model="claude-sonnet-4-6", max_tokens=4096, max_retries=5)
tool_node      = ToolNode([web_search_tool])
llm_with_tools = llm.bind_tools([web_search_tool])

PROMPT_MAP = {
    "jd":        (JD_PARSE_PROMPT,        "jd_raw"),
    "resume":    (RESUME_PARSE_PROMPT,    "resume_raw"),
    "portfolio": (PORTFOLIO_PARSE_PROMPT, "portfolio_raw"),
}


# ── 파일 읽기 ───────────────────────────────────────────────────────

def read_files(state: State) -> dict:
    files = state.get("selected_files", {})
    jd_raw        = read_file(files.get("jd"))
    resume_raw    = read_file(files.get("resume"))
    portfolio_raw = read_file(files.get("portfolio"))
    print(f"📂 파일 읽기 완료  JD:{len(jd_raw)}자  자소서:{len(resume_raw)}자  포트폴리오:{len(portfolio_raw)}자")
    return {
        "jd_raw":        jd_raw,
        "resume_raw":    resume_raw,
        "portfolio_raw": portfolio_raw,
    }


def parse_doc(state: dict) -> dict:
    doc_type = state["doc_type"]
    raw      = state["raw"]
    prompt, key = PROMPT_MAP[doc_type]
    try:
        response = llm.invoke(prompt.format(**{key: raw}))
        parsed = extract_json(response.content)
    except (json.JSONDecodeError, ValueError):
        parsed = {"주요업무": [], "자격요건": [], "우대사항": []} if doc_type == "jd" else {}
    print(f"  ✅ {doc_type} 파싱 완료 → {list(parsed.keys()) if parsed else '(없음)'}")
    return {f"{doc_type}_parsed": parsed}


def merge_parsed(state: State) -> dict:
    jd_p  = state.get("jd_parsed", {})
    re_p  = state.get("resume_parsed", {})
    po_p  = state.get("portfolio_parsed", {})
    print("✅ 파싱 완료 (병렬)")
    print(f"  JD       : {list(jd_p.keys()) if jd_p else '(없음)'}")
    print(f"  자소서    : {list(re_p.keys()) if re_p else '(없음)'}")
    print(f"  포트폴리오: {list(po_p.keys()) if po_p else '(없음)'}")
    return {}


# ── 분석 ────────────────────────────────────────────────────────────

def analyzer(state: State) -> dict:
    jd_parsed        = state.get("jd_parsed", {})
    resume_parsed    = state.get("resume_parsed", {})
    portfolio_parsed = state.get("portfolio_parsed", {})
    search_results   = state.get("search_results", [])
    messages         = state.get("messages", [])

    for msg in messages:
        if hasattr(msg, "content") and isinstance(msg.content, str):
            try:
                parsed = json.loads(msg.content)
                if isinstance(parsed, list):
                    search_results = search_results + parsed
            except (json.JSONDecodeError, TypeError):
                pass

    search_results_str = (
        json.dumps(search_results, ensure_ascii=False, indent=2)
        if search_results
        else "없음"
    )

    response = llm_with_tools.invoke(
        ANALYZER_PROMPT.format(
            jd_parsed=json.dumps(jd_parsed, ensure_ascii=False),
            resume_parsed=json.dumps(resume_parsed, ensure_ascii=False),
            portfolio_parsed=json.dumps(portfolio_parsed, ensure_ascii=False),
            search_results=search_results_str,
        )
    )

    if hasattr(response, "tool_calls") and response.tool_calls:
        print(f"🔍 analyzer — 웹 검색 요청: {[tc['name'] for tc in response.tool_calls]}")
        return {"messages": [response], "search_results": search_results}

    try:
        result = extract_json(response.content)
    except (json.JSONDecodeError, ValueError):
        result = {
            "skill_match": {"matched": [], "missing": []},
            "risk_points": [],
            "jd_keywords": [],
            "experience_highlights": [],
        }

    print("✅ analyzer 완료")
    print(f"  매칭 기술    : {result.get('skill_match', {}).get('matched', [])}")
    print(f"  부족 기술    : {result.get('skill_match', {}).get('missing', [])}")
    print(f"  리스크 포인트: {len(result.get('risk_points', []))}개")
    print(f"  JD 키워드   : {result.get('jd_keywords', [])}")
    if search_results:
        print(f"  웹 검색 반영 : {len(search_results)}건")

    return {
        "skill_match":            result.get("skill_match", {"matched": [], "missing": []}),
        "risk_points":            result.get("risk_points", []),
        "jd_keywords":            result.get("jd_keywords", []),
        "experience_highlights":  result.get("experience_highlights", []),
        "search_results":         search_results,
    }


# ── 질문 생성 ────────────────────────────────────────────────────────

QUESTION_TYPE_RATIOS = {
    "mixed":      (0.40, 0.35, 0.25),
    "tech":       (1.00, 0.00, 0.00),
    "experience": (0.00, 1.00, 0.00),
    "pressure":   (0.00, 0.00, 1.00),
}

DIFFICULTY_INSTRUCTIONS = {
    "mixed":  "difficulty는 전체적으로 easy 20%, medium 50%, hard 30% 비율로 분배하세요.",
    "easy":   "difficulty는 모두 easy로 출제하세요.",
    "medium": "difficulty는 모두 medium으로 출제하세요.",
    "hard":   "difficulty는 모두 hard로 출제하세요.",
}


def questioner(state: State) -> dict:
    cfg                   = state.get("interview_config", {})
    n_base                = int(cfg.get("n_questions", 10))
    question_type         = cfg.get("question_type", "mixed")
    difficulty            = cfg.get("difficulty", "mixed")

    skill_match           = state.get("skill_match", {"matched": [], "missing": []})
    risk_points           = state.get("risk_points", [])
    jd_keywords           = state.get("jd_keywords", [])
    experience_highlights = state.get("experience_highlights", [])
    weak_categories       = state.get("weak_categories", [])

    n_total = n_base + len(weak_categories)

    r_tech, r_exp, r_pres = QUESTION_TYPE_RATIOS.get(question_type, (0.40, 0.35, 0.25))
    n_tech       = round(n_total * r_tech)
    n_experience = round(n_total * r_exp)
    n_pressure   = n_total - n_tech - n_experience

    difficulty_instruction = DIFFICULTY_INSTRUCTIONS.get(difficulty, DIFFICULTY_INSTRUCTIONS["mixed"])

    response = llm.invoke(
        QUESTIONER_PROMPT.format(
            skill_match=json.dumps(skill_match, ensure_ascii=False),
            risk_points=json.dumps(risk_points, ensure_ascii=False),
            jd_keywords=json.dumps(jd_keywords, ensure_ascii=False),
            experience_highlights=json.dumps(experience_highlights, ensure_ascii=False),
            weak_categories=json.dumps(weak_categories, ensure_ascii=False),
            n_tech=n_tech,
            n_experience=n_experience,
            n_pressure=n_pressure,
            difficulty_instruction=difficulty_instruction,
        )
    )

    print("=== Claude 원본 응답 (앞 500자) ===")
    print(response.content[:500])
    print("===================================")

    try:
        question_pool = extract_json(response.content)
        if not isinstance(question_pool, list):
            question_pool = []
    except (json.JSONDecodeError, ValueError) as e:
        print(f"파싱 오류: {e}")
        question_pool = []

    print("✅ questioner 완료")
    print(f"  설정: {question_type}/{difficulty}/{n_base}문항")
    print(f"  총 질문 수: {len(question_pool)}개")
    for q in question_pool:
        print(f"  [{q.get('type', '?')}/{q.get('difficulty', '?')}] {q.get('question', '')}...")

    return {
        "question_pool":    question_pool,
        "total_questions":  len(question_pool),
        "answered_indices": [],   # free_order 모드용 초기화
    }


# ── 면접 진행 ────────────────────────────────────────────────────────

def interviewer(state: State) -> dict:
    cfg            = state.get("interview_config", {})
    interview_mode = cfg.get("interview_mode", "sequential")
    question_pool  = state.get("question_pool", [])

    if interview_mode == "free_order":
        answered_indices = state.get("answered_indices", [])
        remaining = [(i, q) for i, q in enumerate(question_pool) if i not in answered_indices]

        if not remaining:
            # 모든 질문 완료 — evaluator에서 처리
            return {}

        payload = {
            "mode":          "free_order",
            "answered_count": len(answered_indices),
            "total_questions": len(question_pool),
            "questions": [
                {
                    "index":      i,
                    "type":       q.get("type", ""),
                    "difficulty": q.get("difficulty", ""),
                    "question":   q.get("question", ""),
                    "is_retry":   q.get("is_retry", False),
                }
                for i, q in remaining
            ],
        }

        result = interrupt(payload)
        # result: {"selected_index": N, "answer": "..."}
        selected_index = int(result.get("selected_index", remaining[0][0]))
        user_answer    = result.get("answer", "")
        current_question = question_pool[selected_index]

        print(f"✅ interviewer — free_order Q{len(answered_indices) + 1} 답변 수집 (index={selected_index})")
        return {
            "current_question":       current_question,
            "current_answer":         user_answer,
            "current_question_index": selected_index,
        }

    else:
        # sequential (기존 동작)
        answered_count   = state.get("answered_count", 0)
        current_question = question_pool[answered_count]

        payload = {
            "question_number": answered_count + 1,
            "total_questions": len(question_pool),
            "type":       current_question["type"],
            "difficulty": current_question["difficulty"],
            "question":   current_question["question"],
            "intent":     current_question["intent"],
        }
        if current_question.get("hint"):
            payload["hint"]          = current_question["hint"]
            payload["missing_point"] = current_question.get("missing_point", "")

        user_answer = interrupt(payload)

        print(f"✅ interviewer — Q{answered_count + 1} 답변 수집 완료")
        return {
            "current_question": current_question,
            "current_answer":   user_answer,
        }


# ── 코칭 노드 ────────────────────────────────────────────────────────

def hint_provider(state: State) -> dict:
    current_question = state.get("current_question", {})
    current_answer   = state.get("current_answer", "")
    current_score    = state.get("current_score", 0.0)
    question_pool    = state.get("question_pool", [])
    answered_count   = state.get("answered_count", 0)

    response = llm.invoke(
        HINT_PROVIDER_PROMPT.format(
            question=current_question.get("question", ""),
            intent=current_question.get("intent", ""),
            answer=current_answer,
            score=current_score,
        )
    )

    try:
        result = extract_json(response.content)
    except (json.JSONDecodeError, ValueError):
        result = {"hint": "핵심 개념을 다시 생각해보세요.", "missing_point": ""}

    retry_question = {
        **current_question,
        "hint":          result.get("hint", ""),
        "missing_point": result.get("missing_point", ""),
        "is_retry":      True,
    }
    new_pool = list(question_pool)
    cfg = state.get("interview_config", {})
    if cfg.get("interview_mode") == "free_order":
        new_pool.append(retry_question)
    else:
        new_pool.insert(answered_count, retry_question)

    print(f"✅ hint_provider — 힌트 생성 완료")
    print(f"  힌트: {result.get('hint', '')}")
    return {
        "question_pool":   new_pool,
        "total_questions": len(new_pool),
    }


def similar_q(state: State) -> dict:
    current_question = state.get("current_question", {})
    current_answer   = state.get("current_answer", "")
    current_score    = state.get("current_score", 0.0)
    question_pool    = state.get("question_pool", [])
    answered_count   = state.get("answered_count", 0)
    difficulty       = current_question.get("difficulty", "medium")

    response = llm.invoke(
        SIMILAR_Q_PROMPT.format(
            question=current_question.get("question", ""),
            related_keyword=current_question.get("related_keyword", ""),
            difficulty=difficulty,
            q_type=current_question.get("type", "tech"),
            answer=current_answer,
            score=current_score,
        )
    )

    try:
        new_question = extract_json(response.content)
        new_question["id"] = len(question_pool) + 1
    except (json.JSONDecodeError, ValueError):
        new_question = {**current_question, "id": len(question_pool) + 1}

    new_pool = list(question_pool)
    cfg = state.get("interview_config", {})
    if cfg.get("interview_mode") == "free_order":
        new_pool.append(new_question)
    else:
        new_pool.insert(answered_count, new_question)

    print(f"✅ similar_q — 유사 질문 생성 완료")
    print(f"  새 질문: {new_question.get('question', '')}...")
    return {
        "question_pool":   new_pool,
        "total_questions": len(new_pool),
    }


def followup_gen(state: State) -> dict:
    current_question = state.get("current_question", {})
    current_answer   = state.get("current_answer", "")
    current_score    = state.get("current_score", 0.0)
    question_pool    = state.get("question_pool", [])
    answered_count   = state.get("answered_count", 0)

    difficulty_up = {"easy": "medium", "medium": "hard", "hard": "hard"}
    difficulty = difficulty_up.get(current_question.get("difficulty", "medium"), "hard")

    response = llm.invoke(
        FOLLOWUP_GEN_PROMPT.format(
            question=current_question.get("question", ""),
            related_keyword=current_question.get("related_keyword", ""),
            difficulty=difficulty,
            q_type=current_question.get("type", "tech"),
            answer=current_answer,
            score=current_score,
        )
    )

    try:
        new_question = extract_json(response.content)
        new_question["id"] = len(question_pool) + 1
    except (json.JSONDecodeError, ValueError):
        new_question = {**current_question, "id": len(question_pool) + 1}

    new_pool = list(question_pool)
    cfg = state.get("interview_config", {})
    if cfg.get("interview_mode") == "free_order":
        new_pool.append(new_question)
    else:
        new_pool.insert(answered_count, new_question)

    print(f"✅ followup_gen — 심화 질문 생성 완료")
    print(f"  새 질문: {new_question.get('question', '')}...")
    return {
        "question_pool":   new_pool,
        "total_questions": len(new_pool),
    }


# ── 채점 ─────────────────────────────────────────────────────────────

def evaluator(state: State) -> dict:
    current_question = state.get("current_question", {})
    current_answer   = state.get("current_answer", "")
    jd_keywords      = state.get("jd_keywords", [])
    score_history    = state.get("score_history", [])
    weak_categories  = state.get("weak_categories", [])
    session_history  = state.get("session_history", [])
    answered_count   = state.get("answered_count", 0)

    response = llm.invoke(
        EVALUATOR_PROMPT.format(
            question=current_question.get("question", ""),
            intent=current_question.get("intent", ""),
            related_keyword=current_question.get("related_keyword", ""),
            jd_keywords=json.dumps(jd_keywords, ensure_ascii=False),
            answer=current_answer,
        )
    )

    try:
        result = extract_json(response.content)
    except (json.JSONDecodeError, ValueError):
        result = {"score": 5.0, "feedback": "채점 오류", "model_answer": "", "weak_category": ""}

    score         = float(result.get("score", 5.0))
    weak_category = result.get("weak_category", "")

    new_score_history    = score_history + [score]
    new_weak_categories  = weak_categories + ([weak_category] if weak_category else [])
    new_answered_count   = answered_count + 1
    new_session_history  = session_history + [{
        "q_number":    new_answered_count,
        "type":        current_question.get("type", ""),
        "difficulty":  current_question.get("difficulty", ""),
        "question":    current_question.get("question", ""),
        "answer":      current_answer,
        "score":       score,
        "feedback":    result.get("feedback", ""),
        "model_answer": result.get("model_answer", ""),
        "weak_category": weak_category,
    }]

    print(f"✅ evaluator — Q{new_answered_count} 채점 완료: {score}점")
    print(f"  피드백  : {result.get('feedback', '')}")

    update = {
        "current_score":    score,
        "score_history":    new_score_history,
        "weak_categories":  new_weak_categories,
        "answered_count":   new_answered_count,
        "session_history":  new_session_history,
    }

    cfg = state.get("interview_config", {})
    if cfg.get("interview_mode") == "free_order":
        current_question_index = state.get("current_question_index", 0)
        answered_indices       = state.get("answered_indices", [])
        update["answered_indices"] = answered_indices + [current_question_index]

    return update


# ── 결과 리포트 ──────────────────────────────────────────────────────

def report_gen(state: State) -> dict:
    session_history = state.get("session_history", [])
    score_history   = state.get("score_history", [])
    weak_categories = state.get("weak_categories", [])

    avg = sum(score_history) / len(score_history) if score_history else 0

    print("\n" + "=" * 60)
    print("              면접 결과 총정리")
    print("=" * 60)
    print(f"  총 {len(session_history)}문항  |  평균 점수: {avg:.1f} / 10.0")
    print(f"  취약 영역: {list(set(weak_categories)) if weak_categories else '없음'}")
    print("=" * 60)

    for record in session_history:
        score     = record.get("score", 0)
        score_bar = "█" * int(score) + "░" * (10 - int(score))
        print(f"\n[Q{record['q_number']}] [{record['type']}/{record['difficulty']}]  {score:.1f}점  {score_bar}")
        print(f"  질문     : {record['question']}")
        print(f"  내 답변  : {record['answer']}")
        print(f"  피드백   : {record['feedback']}")
        print(f"  모범답안 : {record['model_answer']}")
        print("-" * 60)

    print(f"\n{'✅ 합격권' if avg >= 7 else '📚 보완 필요'} — 평균 {avg:.1f}점")
    return {}
