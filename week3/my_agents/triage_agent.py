import streamlit as st
from agents import (
    Agent,
    RunContextWrapper,
    input_guardrail,
    GuardrailFunctionOutput,
    Runner,
    handoff,
)
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX
from agents.extensions import handoff_filters
from models import HandoffData, InputGuardrailOutput, UserAccountContext

from my_agents.menu_agent import menu_agent
from my_agents.order_agent import order_agent
from my_agents.reservation_agent import reservation_agent

input_guardrail_agent = Agent(
    name="Input Guardrail Agent",
    instructions="""
    당신은 레스토랑 서비스에 들어오는 사용자 입력을 검사하는 가드레일 에이전트입니다.

    당신의 역할은 사용자의 입력이 레스토랑 서비스(메뉴, 주문, 예약)와 관련된 내용인지 판단하는 것입니다.

    판단 기준:
    - 허용: 메뉴 조회, 음식 재료/알레르기 관련 질문, 주문 생성/조회/변경, 테이블 예약 관련 요청
    - 차단: 레스토랑 서비스와 무관한 모든 요청 (예: 날씨, 정치, 코드 작성, 일반 잡담 등)

    반드시 다음 JSON 형식으로만 응답하세요:
    {
        "is_topic_off": true 또는 false,
        "reason": "판단 이유를 한 문장으로 작성"
    }

    - is_topic_off: true → 레스토랑 서비스와 무관한 요청이므로 차단
    - is_topic_off: false → 레스토랑 서비스와 관련된 요청이므로 처리 가능
    """,
    output_type=InputGuardrailOutput,
)


@input_guardrail
async def off_topic_guardrail(
    wrapper: RunContextWrapper[UserAccountContext],
    agent: Agent[UserAccountContext],
    input: str | list,
):
    # input이 list인 경우 마지막 사용자 메시지 텍스트만 추출
    if isinstance(input, list):
        user_text = next(
            (
                item.get("content", "") if isinstance(item, dict) else ""
                for item in reversed(input)
                if (isinstance(item, dict) and item.get("role") == "user")
            ),
            "",
        )
        if isinstance(user_text, list):
            user_text = " ".join(
                part.get("text", "") for part in user_text if isinstance(part, dict)
            )
    else:
        user_text = input

    result = await Runner.run(
        input_guardrail_agent,
        user_text,
        context=wrapper.context,
    )

    return GuardrailFunctionOutput(
        output_info=result.final_output,
        tripwire_triggered=result.final_output.is_off_topic,
    )


def dynamic_triage_agent_instructions(
    wrapper: RunContextWrapper[UserAccountContext],
    agent: Agent[UserAccountContext],
):
    return f"""
    {RECOMMENDED_PROMPT_PREFIX}
    당신은 레스토랑에서 손님을 돕는 에이전트입니다. 당신은 손님의 질문이나 요청을 듣고, 알맞는 에이전트를 연결해주는 역할입니다.
    
    해당 손님의 이름은 {wrapper.context.name}입니다.

    당신은 아래의 에이전트들을 연결해줄 수 있습니다:
    
    1. 메뉴 에이전트
    - 메뉴 에이전트는 메뉴, 재료, 알레르기 관련 질문에 답변하는 에이전트입니다.
    - 예시 질문: "오늘의 메뉴는 뭔가요?", "채식 메뉴가 있나요?", "제가 견과류 알레르기가 있는데, 이에 해당하지 않는 메뉴가 있나요?"
    
    2. 주문 에이전트
    - 주문 에이전트는 주문을 받고 확인하는 에이전트입니다.
    - 예시 질문: "주문을 하고 싶어요", "제가 주문한 내용을 확인하고 싶어요", "주문을 변경하고 싶어요"
    
    3. 예약 에이전트
    - 예약 에이전트는 테이블 예약 처리를 담당하는 에이전트입니다.
    - 예시 질문: "예약을 하고 싶어요", "오늘 저녁 7시에 4인 예약이 가능한가요?"
    
    분류 규칙은 다음과 같습니다:
    1. 손님의 질문이나 요청을 듣는다.
    2. 손님의 질문이나 요청이 **메뉴/주문/예약** 관련 질문이 아니라면 "죄송하지만, 저는 메뉴, 주문, 예약 관련 질문에만 답변할 수 있습니다."라고 답변한다.
    3. 에이전트를 연결할 때 에이전트 이름과 함께 연결시킨다.
    """


def handle_handoff(
    wrapper: RunContextWrapper[UserAccountContext],
    input_data: HandoffData,
):
    """
    Handoff 발생 시 실행되는 콜백 함수
    Session state에 handoff 정보를 저장하여 main.py에서 처리할 수 있도록 함
    """
    # Streamlit session state에 handoff 정보 저장
    if "pending_handoff" not in st.session_state:
        st.session_state.pending_handoff = {}

    # 원본 사용자 메시지 가져오기
    original_message = st.session_state.get("original_user_message", "")

    # Handoff 정보 저장
    st.session_state.pending_handoff = {
        "to_agent": input_data.to_agent_name,
        "reason": input_data.reason,
        "issue_type": input_data.issue_type,
        "issue": input_data.issue_description,
        "original_message": original_message,
    }

    # 사이드바에 handoff 정보 표시 (디버깅용)
    with st.sidebar:
        with st.expander("🔄 Latest Handoff", expanded=True):
            st.write(f"**To:** {input_data.to_agent_name}")
            st.write(f"**Reason:** {input_data.reason}")
            st.write(f"**Type:** {input_data.issue_type}")
            st.write(f"**Issue:** {input_data.issue_description}")

    return input_data


def make_handoff(agent: Agent, description: str):
    """
    Handoff 객체 생성 헬퍼 함수
    """
    return handoff(
        agent=agent,
        tool_description_override=description,
        on_handoff=handle_handoff,
        input_type=HandoffData,
        input_filter=handoff_filters.remove_all_tools,
    )


menu_agent_description = """
메뉴, 음식 재료, 알레르기 관련 질문을 처리하는 에이전트입니다.
다음과 같은 경우에 이 에이전트로 handoff하세요:
- 오늘의 메뉴나 특정 메뉴 항목에 대해 묻는 경우
- 채식, 비건, 글루텐프리 등 식이 제한에 맞는 메뉴를 찾는 경우
- 특정 음식의 재료나 조리 방법을 묻는 경우
- 알레르기 유발 성분(견과류, 유제품, 해산물 등) 포함 여부를 확인하는 경우
- 메뉴 가격이나 칼로리 정보를 묻는 경우
"""

order_agent_description = """
주문 생성, 조회, 변경, 취소를 처리하는 에이전트입니다.
다음과 같은 경우에 이 에이전트로 handoff하세요:
- 음식을 주문하고 싶은 경우
- 현재 주문 내역을 확인하거나 조회하는 경우
- 기존 주문에 항목을 추가하거나 변경하는 경우
- 주문을 취소하고 싶은 경우
- 주문 상태(준비 중, 완료 등)를 확인하는 경우
"""

reservation_agent_description = """
테이블 예약 생성, 조회, 변경, 취소를 처리하는 에이전트입니다.
다음과 같은 경우에 이 에이전트로 handoff하세요:
- 특정 날짜와 시간에 테이블을 예약하고 싶은 경우
- 인원수에 맞는 테이블 가용 여부를 확인하는 경우
- 기존 예약을 조회하거나 변경하는 경우
- 예약을 취소하고 싶은 경우
- 단체석, 프라이빗룸 등 특별한 좌석을 요청하는 경우
"""


triage_agent = Agent(
    name="Triage Agent",
    instructions=dynamic_triage_agent_instructions,
    input_guardrails=[off_topic_guardrail],
    handoffs=[
        make_handoff(menu_agent, menu_agent_description),
        make_handoff(order_agent, order_agent_description),
        make_handoff(reservation_agent, reservation_agent_description),
    ],
)

# sub-agent 간 직접 handoff 설정 (순환 참조 방지를 위해 triage_agent 생성 후 설정)
menu_agent.handoffs = [
    make_handoff(order_agent, order_agent_description),
    make_handoff(reservation_agent, reservation_agent_description),
]
order_agent.handoffs = [
    make_handoff(menu_agent, menu_agent_description),
    make_handoff(reservation_agent, reservation_agent_description),
]
reservation_agent.handoffs = [
    make_handoff(menu_agent, menu_agent_description),
    make_handoff(order_agent, order_agent_description),
]
