"""Escalation briefing agent — the demo showstopper.

When a case goes to a human, this agent produces a structured brief so the human
resolves it faster (measurable handle-time savings). It summarizes the issue,
reads sentiment, notes what was tried, and recommends an action — the human still
decides. This is what turns "handoff" from a dead end into a value-add.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from config import AGENT_MODEL
from src import llm
from src.logging_utils import Trace


class CaseBrief(BaseModel):
    issue: str = Field(description="1-2 sentence summary of the customer's problem")
    sentiment: str = Field(description="calm | frustrated | angry | distressed")
    urgency: str = Field(description="low | medium | high | critical")
    what_was_tried: str = Field(description="Automated steps already attempted, or 'none'")
    recommended_action: str = Field(description="Suggested next step for the human agent")


_SYSTEM = (
    "You prepare a concise handoff brief for a human support agent. Read the "
    "customer's message and any routing notes, then fill the schema so the human "
    "can act immediately without re-reading the whole thread."
)


def brief(message: str, routing_note: str, trace: Trace) -> CaseBrief:
    user = f"Routing note: {routing_note}\n\nCustomer message: {message}"
    result, in_tok, out_tok = llm.parse(
        AGENT_MODEL, CaseBrief, _SYSTEM, user, max_tokens=500)
    trace.input_tokens += in_tok
    trace.output_tokens += out_tok
    return result
