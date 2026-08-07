"""Central configuration and the intent taxonomy.

The taxonomy is the heart of the project — the router classifies every message
into one of INTENTS, and the confidence threshold decides when we escalate to a
human instead of guessing. This file is the single source of truth for both the
router and the evaluation harness.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
KB_DIR = DATA_DIR / "knowledge_base"
KB_INDEX = DATA_DIR / "kb_index.pkl"
LOG_FILE = DATA_DIR / "events.jsonl"
TESTSET = DATA_DIR / "labeled_testset.csv"
SOURCE_CSV = ROOT / "customer_support_tickets.csv"

# --- Models (OpenRouter slugs) ----------------------------------------------
# Router is latency/cost-critical -> Haiku. Agents need more quality -> Sonnet.
# Override in .env. Browse slugs at https://openrouter.ai/models
ROUTER_MODEL = os.getenv("ROUTER_MODEL", "anthropic/claude-haiku-4.5")
AGENT_MODEL = os.getenv("AGENT_MODEL", "anthropic/claude-sonnet-4.6")

# --- Routing ----------------------------------------------------------------
# The "triage nurse" rule: below this confidence, we do NOT guess -> human handoff.
ROUTER_CONFIDENCE_THRESHOLD = float(os.getenv("ROUTER_CONFIDENCE_THRESHOLD", "0.75"))

# --- Sentiment fast-track (churn protection) --------------------------------
# A strongly angry/distressed customer is fast-tracked to a human even when the
# router is otherwise confident — catching at-risk customers early cuts churn.
SENTIMENT_FASTTRACK = {"angry", "distressed"}
SENTIMENT_INTENSITY_THRESHOLD = float(os.getenv("SENTIMENT_INTENSITY_THRESHOLD", "0.8"))

# --- Transaction policy (business-rules engine) -----------------------------
# Refunds at or below this (and with no risk flags) are auto-approvable; above
# it, or anything risky, requires a human. The bot never executes either way.
AUTO_APPROVE_LIMIT = float(os.getenv("AUTO_APPROVE_LIMIT", "2000"))  # USD
# Idempotency: suppress duplicate requests seen within this window.
IDEMPOTENCY_STORE = DATA_DIR / "idempotency.json"
IDEMPOTENCY_TTL_HOURS = float(os.getenv("IDEMPOTENCY_TTL_HOURS", "24"))

# The 4 router buckets. These are ACTIONS, not topics. Keep descriptions tight —
# they are injected into the router prompt verbatim.
INTENTS: dict[str, str] = {
    "faq": "General/how-to questions answerable from a knowledge base "
           "(policies, product info, billing explanations). No account change needed.",
    "empathy": "Emotionally-toned messages where tone matters more than any task: "
               "frustration/distress to de-escalate, OR positive appreciation, "
               "thanks, compliments, and friendly chit-chat to acknowledge warmly.",
    "transaction": "Requests to take an account action: cancel, refund, change "
                   "plan, update details. Has real-world side effects.",
    "handoff": "Complex, ambiguous, high-risk, or out-of-scope cases that a bot "
               "should not attempt. When unsure, route here.",
}

# Maps the dataset's `Ticket Type` (a TOPIC) to a rough router bucket (an ACTION).
# Used ONLY to seed the eval test set — teammates hand-correct the ambiguous ones.
# NOTE: empathy/handoff are driven by priority + sentiment, not ticket type, so
# the mapping intentionally can't produce them. That gap is the teaching point.
TICKET_TYPE_TO_INTENT: dict[str, str] = {
    "Billing inquiry": "faq",
    "Product inquiry": "faq",
    "Technical issue": "faq",
    "Cancellation request": "transaction",
    "Refund request": "transaction",
}
