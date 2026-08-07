"""Handoff agent — hands the case to a human WITH a briefing.

Never a dead end: it always attaches an escalation brief (see
escalation_briefing) so the human starts informed. Returns the customer-facing
holding message; the brief is logged on the trace for the agent console.
"""
from __future__ import annotations

from src import llm
from src.agents import escalation_briefing
from src.logging_utils import Trace

_CUSTOMER_REPLY = (
    "Thanks for reaching out — I'm connecting you with a specialist who can help "
    "with this properly. They'll have the full context of your message, so you "
    "won't need to repeat yourself."
)


def handle(message: str, trace: Trace, routing_note: str = "") -> str:
    trace.escalated = True
    # The brief is a value-add, not a hard dependency. If the LLM is unavailable
    # (outage, bad key, bad model slug), we STILL hand off to a human cleanly —
    # never crash on a customer. That is the whole point of the handoff path.
    try:
        case = escalation_briefing.brief(message, routing_note, trace)
        trace.outcome = (f"handoff | sentiment={case.sentiment} "
                         f"urgency={case.urgency} | rec={case.recommended_action}")
    except llm.LLMUnavailable as e:
        trace.fallback_used = True
        trace.outcome = f"handoff | brief_unavailable:{e}"
    return _CUSTOMER_REPLY
