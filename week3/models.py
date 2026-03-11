from pydantic import BaseModel
from typing import Optional


class UserAccountContext(BaseModel):
    customer_id: int
    name: str


class InputGuardrailOutput(BaseModel):
    is_topic_off: bool
    is_unacceptable_language: bool
    reason: Optional[str] = None


class OutputGuardrailOutput(BaseModel):
    is_topic_off: bool
    is_internal_info_leak: bool
    reason: Optional[str] = None


class HandoffData(BaseModel):
    to_agent_name: str
    issue_type: str
    issue_description: str
    reason: str
