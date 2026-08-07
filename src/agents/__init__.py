"""Layer 3: the downstream agents.

Each agent exposes `handle(message, trace) -> str`. The pipeline dispatches to
exactly one based on the router's intent. Keep these focused — the router already
decided WHAT this message needs; an agent just does that one thing well.
"""
from src.agents import empathy, faq, handoff, transaction, escalation_briefing

__all__ = ["faq", "empathy", "transaction", "handoff", "escalation_briefing"]
