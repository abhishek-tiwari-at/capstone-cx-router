"""Layer 2: the micro-intent router — the heart of the project.

Classifies each message into one of config.INTENTS with a confidence score, a
one-line reason, AND the customer's emotional tone — all in a single model call.

Two deterministic safety overrides then run in code (not the model):
  1. Confidence floor: below the threshold, we escalate instead of guessing.
  2. Sentiment fast-track: a strongly angry/distressed customer goes straight to
     a human even if the router is confident — catching at-risk customers early
     protects against churn.

Both are the "triage nurse" reflex: when a case is risky, don't guess — escalate.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from config import (INTENTS, ROUTER_CONFIDENCE_THRESHOLD, ROUTER_MODEL,
                    SENTIMENT_FASTTRACK, SENTIMENT_INTENSITY_THRESHOLD)
from src import llm


class RouteDecision(BaseModel):
    intent: str = Field(description="One of: " + ", ".join(INTENTS))
    confidence: float = Field(ge=0.0, le=1.0,
                              description="0-1 certainty in the chosen intent")
    reason: str = Field(description="One short sentence justifying the choice")
    sentiment: str = Field(
        description="Customer tone: positive | neutral | frustrated | angry | distressed")
    sentiment_intensity: float = Field(
        ge=0.0, le=1.0,
        description="Strength of negative emotion, 0.0 if calm/positive, 1.0 if furious")


def _system_prompt() -> str:
    lines = ["You are a customer-experience triage router. You do NOT answer the",
             "customer. You classify their message into exactly one intent and read",
             "their emotional tone.", "", "Intents:"]
    for name, desc in INTENTS.items():
        lines.append(f"- {name}: {desc}")
    lines += [
        "",
        "Rules:",
        "- Judge the ACTION needed, not just the topic. Topic words like 'refund' "
        "  or 'cancel' do NOT by themselves mean 'transaction' — ask whether the "
        "  customer wants INFORMATION (-> faq) or wants us to DO something now "
        "  (-> transaction).",
        "  e.g. 'how long will my refund take' -> faq (asking about timing/policy).",
        "  e.g. 'how do I cancel my subscription' -> faq (asking how-to/policy).",
        "  e.g. 'please refund my order #123' -> transaction (asking us to act).",
        "  e.g. 'cancel my subscription' -> transaction (asking us to act).",
        "- Warm, positive, or appreciative messages (thanks, compliments, "
        "  'I love you guys', friendly chit-chat) with no task are 'empathy' —",
        "  respond warmly. Never escalate a happy customer to a human.",
        "- Be honest about confidence. If the message is vague, mixed, or risky,",
        "  give low confidence — the system will escalate to a human.",
        "- Also classify sentiment and sentiment_intensity. Reserve 'angry' and",
        "  'distressed' with high intensity for genuinely upset, threatening-to-leave,",
        "  or panicked customers — not mild annoyance (that is 'frustrated').",
        "- Never invent an intent outside the list.",
    ]
    return "\n".join(lines)


def _apply_safety_overrides(decision: RouteDecision) -> RouteDecision:
    """Deterministic, testable escalation rules layered on the model's output."""
    if decision.intent not in INTENTS:
        decision.intent = "handoff"
        decision.reason = f"unknown label normalized to handoff: {decision.reason}"

    # 1. Confidence floor. A clearly POSITIVE, low-stakes message is not a risky
    #    ambiguity — handle it warmly (empathy) instead of escalating a happy
    #    customer to a human. Everything else low-confidence escalates.
    if decision.confidence < ROUTER_CONFIDENCE_THRESHOLD and decision.intent != "handoff":
        if decision.sentiment == "positive":
            decision.reason = (f"low confidence ({decision.confidence:.2f}) but positive "
                               f"tone; handled warmly. [original: {decision.intent}] "
                               f"{decision.reason}")
            decision.intent = "empathy"
        else:
            decision.reason = (f"low confidence ({decision.confidence:.2f} < "
                               f"{ROUTER_CONFIDENCE_THRESHOLD}); escalating. "
                               f"[original: {decision.intent}] {decision.reason}")
            decision.intent = "handoff"

    # 2. Sentiment fast-track (churn protection).
    if (decision.sentiment in SENTIMENT_FASTTRACK
            and decision.sentiment_intensity >= SENTIMENT_INTENSITY_THRESHOLD
            and decision.intent != "handoff"):
        decision.reason = (f"churn risk: {decision.sentiment} "
                           f"({decision.sentiment_intensity:.2f}) — fast-tracked to a "
                           f"human. [original: {decision.intent}] {decision.reason}")
        decision.intent = "handoff"

    return decision


def route(message: str) -> tuple[RouteDecision, int, int]:
    """Return (decision, input_tokens, output_tokens) with safety overrides applied."""
    decision, in_tok, out_tok = llm.parse(
        model=ROUTER_MODEL,
        schema=RouteDecision,
        system=_system_prompt(),
        user=message,
        max_tokens=300,
    )
    return _apply_safety_overrides(decision), in_tok, out_tok
