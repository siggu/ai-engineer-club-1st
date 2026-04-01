from typing import cast
from app.graph.state import AppState, UserConfig, DEFAULT_USER_CONFIG


def user_config(state: AppState) -> dict:
    """
    유저 설정을 받아 AppState에 반영하는 노드.
    유저가 직접 설정한 값은 유지하고, 없는 항목은 기본값으로 채운다.
    """
    incoming: dict = state.get("user_config") or {}
    merged = cast(UserConfig, {**DEFAULT_USER_CONFIG, **incoming})

    return {
        "user_config": merged,
        "current_question_depth": 0,
        "current_base_question": "",
    }
