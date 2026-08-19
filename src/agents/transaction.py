"""Transaction agent — order-grounded, human-in-the-loop, policy + idempotency.

The language model NEVER executes anything. It extracts a proposed action; then
deterministic layers decide what happens:

  1. order lookup   -> the refund AMOUNT is the order's REAL value, not the
                       customer's claim (authoritative input to the policy).
  2. access control -> if we know who's asking and they don't OWN the order,
                       block it (you can't act on someone else's order).
  3. policy.decide  -> small clean refund is auto-approvable; else human.
  4. idempotency    -> suppress duplicate requests within the TTL window.

The bot still executes nothing — "auto-approvable" only means it could be sent to
a payments backend without a human, once that backend exists.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from config import AGENT_MODEL
from src import guardrails, idempotency, llm, orders, policy
from src.logging_utils import Trace

_ACTIONS = ["refund", "cancellation", "plan_change", "detail_update", "unclear"]


class ProposedAction(BaseModel):
    action: str = Field(description="One of: " + ", ".join(_ACTIONS))
    summary: str = Field(description="One line describing what the customer wants")
    amount: float | None = Field(
        default=None, description="Amount in USD if the customer stated one, else null")
    order_reference: str | None = Field(
        default=None, description="Order id if the customer gave one (e.g. ORD-1001), else null")


_SYSTEM = (
    "You are a transaction intake agent. You do NOT execute anything and you do NOT "
    "compose any reply to the customer. Only extract the customer's requested account "
    "action into the schema, including the order id and amount if stated (null otherwise)."
)

# Deterministic, policy-derived customer copy. The LLM only extracts structured
# fields above — it must never author the reply, since it has no way to know
# whether the policy engine will auto-approve or require a human (see policy.py).
_ACTION_LABELS = {
    "refund": "refund request",
    "cancellation": "cancellation request",
    "plan_change": "plan change request",
    "detail_update": "detail update request",
    "unclear": "request",
}


def _auto_approved_message(action: str, order: "orders.Order | None") -> str:
    label = _ACTION_LABELS.get(action, "request")
    order_note = f" for order {order.order_id}" if order else ""
    return (f"Good news — your {label}{order_note} has been approved and queued for "
            f"processing. No human review needed for this one; you'll get a "
            f"confirmation once it's complete.")


def handle(message: str, trace: Trace, current_user: str | None = None) -> str:
    action, in_tok, out_tok = llm.parse(
        AGENT_MODEL, ProposedAction, _SYSTEM, message, max_tokens=400)
    trace.input_tokens += in_tok
    trace.output_tokens += out_tok

    order = orders.get(action.order_reference)

    # Access control: if we know who is asking and they don't own the order, stop.
    if order and current_user and not orders.owns(order.order_id, current_user):
        trace.agent = "handoff"
        trace.escalated = True
        trace.guardrail_blocks.append("ownership_mismatch")
        trace.outcome = f"blocked:ownership_mismatch:{order.order_id}"
        return ("For your security I can't act on an order that isn't linked to your "
                "account. I'm connecting you with a specialist to verify your identity.")

    # Order referenced but not found -> ask rather than guess.
    if action.order_reference and not order:
        trace.outcome = f"order_not_found:{action.order_reference}"
        return ("I couldn't find an order with that ID. Could you double-check the "
                "order number so I can help?")

    # Authoritative amount: the order's real value beats the customer's claim.
    amount = order.value if order else action.amount

    risk_flags: list[str] = []
    pii_found = guardrails.detect_pii(message)
    if pii_found:
        risk_flags.append("pii_in_message")
        trace.guardrail_blocks.extend(pii_found)
        trace.agent = "handoff"
        trace.escalated = True
        return ("I detected sensitive payment information in your message. For security, "
                "I'm connecting you with a specialist who can help you safely.")

    decision = policy.decide(action=action.action, amount=amount, risk_flags=risk_flags)

    idem_ref = order.order_id if order else action.order_reference
    key = idempotency.make_key(action.action, idem_ref, amount, message)
    is_dupe, _ = idempotency.check_and_record(
        key, {"route": decision.route, "action": action.action})

    if is_dupe:
        trace.outcome = f"duplicate_suppressed:{action.action}:idem={key}"
        return ("It looks like we already have this request on file and our team is "
                "on it — no need to resubmit.")

    if decision.route == "human":
        trace.escalated = True

    order_note = (f" order={order.order_id} value=${order.value:,.2f}" if order else "")
    trace.outcome = (f"proposed_action:{action.action}:amount={amount}:"
                     f"route={decision.route}:idem={key}{order_note} | {decision.reason}")

    if decision.route == "human":
        return ("Thanks — I've logged your request, but an action of this size or "
                "type needs a quick human review before it can go through. A "
                "specialist will follow up with you shortly.")
    return _auto_approved_message(action.action, order)
