from pydantic import BaseModel
from typing import Literal


class TriageOutput(BaseModel):
    category: Literal["BOOKING", "QUOTE", "COMPLAINT", "EMERGENCY", "BILLING", "OUT_OF_SCOPE"]
    priority: Literal["P1", "P2", "P3"]
    route_to: Literal["Dispatch", "Sales", "Accounts", "Customer Care", "Customer Care + Accounts"]
    draft_reply: str
    needs_human_review: bool
    reasoning: str