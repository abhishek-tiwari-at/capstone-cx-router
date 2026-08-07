"""Empathy agent — de-escalates tone, does not take actions.

Its job is to acknowledge feeling and buy calm, then guide toward a next step.
It must never promise a fix or claim an account action was taken.
"""
from __future__ import annotations

from config import AGENT_MODEL
from src import llm
from src.logging_utils import Trace

_SYSTEM = (
    "You are a warm customer-experience agent. Match the customer's emotional tone:\n"
    "- If they are upset or frustrated: acknowledge it genuinely, take ownership, and "
    "offer a concrete next step.\n"
    "- If they are positive or appreciative (thanks, compliments, friendly chit-chat): "
    "thank them warmly and briefly, and invite them to reach out anytime.\n"
    "Keep it to 2-4 sentences. Never promise refunds, cancellations, or any account "
    "change — you cannot perform those — and never claim an action has been done."
)


def handle(message: str, trace: Trace) -> str:
    reply, in_tok, out_tok = llm.complete(AGENT_MODEL, _SYSTEM, message, max_tokens=400)
    trace.input_tokens += in_tok
    trace.output_tokens += out_tok
    return reply
