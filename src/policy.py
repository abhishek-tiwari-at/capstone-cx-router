"""Transaction policy engine — deterministic business rules.

Sits between the transaction agent (which only *extracts* a request) and the
outcome (what actually happens). The language model proposes; this module — plain
Python, fully auditable — decides the route. No LLM here on purpose: money
decisions should be deterministic and testable, not probabilistic.

Rule: a refund at or below AUTO_APPROVE_LIMIT with no risk flags is
auto-approvable; anything larger, or with any risk flag, requires a human. The
bot still executes nothing either way — "auto-approvable" means it *could* be
sent to the payments backend without a human, once that backend exists.
"""
from __future__ import annotations

from dataclasses import dataclass

from config import AUTO_APPROVE_LIMIT

MONEY_ACTIONS = {"refund"}


@dataclass
class PolicyDecision:
    route: str   # "auto_approvable" | "human"
    reason: str


def decide(*, action: str, amount: float | None,
           risk_flags: list[str]) -> PolicyDecision:
    if risk_flags:
        return PolicyDecision("human",
                              f"risk flags force human: {', '.join(risk_flags)}")

    if action in MONEY_ACTIONS:
        if amount is None:
            return PolicyDecision("human",
                                  "refund amount not specified; cannot verify limit")
        if amount > AUTO_APPROVE_LIMIT:
            return PolicyDecision(
                "human",
                f"refund ${amount:,.2f} exceeds ${AUTO_APPROVE_LIMIT:,.0f} "
                "auto-approve limit")
        return PolicyDecision(
            "auto_approvable",
            f"refund ${amount:,.2f} within ${AUTO_APPROVE_LIMIT:,.0f} limit, "
            "no risk flags")

    if action in ("plan_change", "detail_update"):
        return PolicyDecision("auto_approvable", "low-risk non-financial change")

    # cancellation, unclear, or anything unexpected -> human by default.
    return PolicyDecision("human", f"'{action}' routed to human by policy")
