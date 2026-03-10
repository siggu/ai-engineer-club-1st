from pydantic import BaseModel
from typing import Optional


class UserAccountContext(BaseModel):
    customer_id: int
    name: str


class InputGuardrailOutput(BaseModel):
    is_off_topic: bool
    reason: Optional[str] = None


class HandoffData(BaseModel):
    to_agent_name: str
    issue_type: str
    issue_description: str
    reason: str
