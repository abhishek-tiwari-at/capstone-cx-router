"""The orchestrator: wires all six enterprise layers into one pass.

  input guardrails -> router -> agent (RAG/HITL) -> output guardrails
                    -> fallbacks around every step -> one structured trace

Every failure path degrades to a human handoff rather than crashing on a
customer. Returns (customer_reply, trace) so callers (CLI, eval, future UI) can
show both the answer and the decision metadata.
"""
from __future__ import annotations

from config import SENTIMENT_FASTTRACK, SENTIMENT_INTENSITY_THRESHOLD
from src import guardrails, llm, case_review
from src.agents import empathy, faq, handoff, transaction
from src.logging_utils import Trace, trace_scope
from src.router import route

AI_DISCLOSURE = "(You're chatting with an AI assistant.) "


def handle_message(message: str, channel: str = "cli",
                   current_user: str | None = None, vertical: str = "ecommerce") -> tuple[str, Trace]:
    with trace_scope(channel=channel) as trace:
        trace.actor = current_user
        trace.redacted_input = guardrails.redact_pii(message)

        # --- Layer 1: input guardrails ---
        gate = guardrails.check_input(message)
        if not gate.allowed:
            trace.guardrail_blocks.append(gate.reason)
            reply = handoff.handle(message, trace,
                                   routing_note=f"input_guardrail:{gate.reason}")
            trace.finish("blocked_input_to_handoff")
            return _finalize(reply, trace)

        # --- Layer 2: router (with fallback to handoff) ---
        try:
            decision, in_tok, out_tok = route(message)
            trace.input_tokens += in_tok
            trace.output_tokens += out_tok
            trace.intent = decision.intent
            trace.confidence = decision.confidence
            trace.router_reason = decision.reason
            trace.sentiment = decision.sentiment
            trace.sentiment_intensity = decision.sentiment_intensity
            trace.churn_risk = (
                decision.sentiment in SENTIMENT_FASTTRACK
                and decision.sentiment_intensity >= SENTIMENT_INTENSITY_THRESHOLD)
        except llm.LLMUnavailable as e:
            trace.fallback_used = True
            reply = handoff.handle(message, trace, routing_note=f"router_failed:{e}")
            trace.finish("router_failure_to_handoff")
            return _finalize(reply, trace)

        # --- Layer 3: dispatch to exactly one agent ---
        reply = _dispatch(decision.intent, message, trace, decision.reason, current_user, vertical)

        if trace.outcome is None:
            trace.finish(f"handled_by:{trace.agent}")
        return _finalize(reply, trace)


def _dispatch(intent: str, message: str, trace: Trace, note: str,
              current_user: str | None = None, vertical: str = "ecommerce") -> str:
    trace.agent = intent
    try:
        if intent == "faq":
            try:
                return faq.handle(message, trace, vertical=vertical)
            except faq.AbstainError as e:
                # Grounding abstain -> escalate with a brief.
                trace.agent = "handoff"
                return handoff.handle(message, trace, routing_note=f"faq_abstain:{e}")
        if intent == "empathy":
            return empathy.handle(message, trace)
        if intent == "transaction":
            return transaction.handle(message, trace, current_user)
        # intent == "handoff" or anything unexpected
        trace.agent = "handoff"
        return handoff.handle(message, trace, routing_note=note)
    except llm.LLMUnavailable as e:
        trace.fallback_used = True
        trace.agent = "handoff"
        return handoff.handle(message, trace, routing_note=f"agent_failed:{e}")


def _finalize(reply: str, trace: Trace) -> tuple[str, Trace]:
    # --- Layer 4: output guardrails ---
    check = guardrails.check_output(reply)
    if not check.safe:
        trace.guardrail_blocks.append(check.reason)
        reply = ("I've noted your request and a specialist will confirm the details "
                 "with you shortly.")
    trace.redacted_response = guardrails.redact_pii(reply)

    # --- Case review (tracks failures for improvement loop) ---
    case_review.log_case_review(trace)

    return AI_DISCLOSURE + reply, trace
