"""Case review system: tracks failure patterns to fuel improvement loops.

Every message produces a trace. This layer watches for failures (FAQ abstentions,
misroutes, escalations, guardrail blocks) and aggregates them into actionable
insights: "these are our knowledge-base gaps," "these intents get misrouted,"
"these are false positives for guardrails."

The feedback loop: failures → aggregation → human review → action (add KB doc,
retrain router, tune thresholds) → replay to measure impact.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.logging_utils import Trace

CASE_REVIEW_FILE = Path("data/case_review.jsonl")


@dataclass
class CaseReviewRecord:
    """A single failure or noteworthy event captured for review."""
    trace_id: str
    ts: float
    actor: str | None
    category: str  # "faq_abstain", "misroute", "escalation", "guardrail_block"
    message: str  # redacted input
    intent: str | None
    confidence: float | None
    reason: str  # why it was logged (e.g., "no_kb_match", "sentiment_fasttrack")
    agent: str | None
    action_taken: str | None  # e.g., "escalated_to_human"
    metadata: dict[str, Any] = None  # extra context (e.g., sentiment, confidence)


def log_case_review(trace: Trace) -> None:
    """Examine a trace and log failures/noteworthy patterns."""
    if trace.outcome is None:
        return

    records = []

    # --- FAQ abstention (knowledge-base gap) ---
    # Detected when: router classified as "faq", but FAQ agent found no KB match and escalated to handoff
    if (trace.intent == "faq" and trace.agent == "handoff" and not trace.fallback_used):
        records.append(CaseReviewRecord(
            trace_id=trace.trace_id,
            ts=trace.ts_start,
            actor=trace.actor,
            category="faq_abstain",
            message=trace.redacted_input,
            intent=trace.intent,
            confidence=trace.confidence,
            reason="no_kb_match",
            agent="handoff",
            action_taken="escalated_to_human",
            metadata={
                "sentiment": trace.sentiment,
                "sentiment_intensity": trace.sentiment_intensity,
            }
        ))

    # --- Escalation due to low confidence (calibration opportunity) ---
    if (trace.confidence is not None and trace.confidence < 0.75 and
        trace.agent == "handoff" and "faq_abstain" not in (trace.router_reason or "")):
        records.append(CaseReviewRecord(
            trace_id=trace.trace_id,
            ts=trace.ts_start,
            actor=trace.actor,
            category="low_confidence_escalation",
            message=trace.redacted_input,
            intent=trace.intent,
            confidence=trace.confidence,
            reason="below_confidence_floor",
            agent="handoff",
            action_taken="escalated_to_human",
            metadata={"router_reason": trace.router_reason}
        ))

    # --- Churn risk (sentiment fast-track) ---
    if trace.churn_risk:
        records.append(CaseReviewRecord(
            trace_id=trace.trace_id,
            ts=trace.ts_start,
            actor=trace.actor,
            category="churn_risk",
            message=trace.redacted_input,
            intent=trace.intent,
            confidence=trace.confidence,
            reason="sentiment_fasttrack",
            agent=trace.agent,
            action_taken="escalated_to_human",
            metadata={
                "sentiment": trace.sentiment,
                "sentiment_intensity": trace.sentiment_intensity,
            }
        ))

    # --- Guardrail blocks (safety incidents) ---
    if trace.guardrail_blocks:
        for block in trace.guardrail_blocks:
            records.append(CaseReviewRecord(
                trace_id=trace.trace_id,
                ts=trace.ts_start,
                actor=trace.actor,
                category="guardrail_block",
                message=trace.redacted_input,
                intent=trace.intent,
                confidence=trace.confidence,
                reason=block,
                agent=trace.agent,
                action_taken="blocked",
                metadata={"all_blocks": trace.guardrail_blocks}
            ))

    # --- Fallback used (reliability issue) ---
    if trace.fallback_used:
        records.append(CaseReviewRecord(
            trace_id=trace.trace_id,
            ts=trace.ts_start,
            actor=trace.actor,
            category="fallback_used",
            message=trace.redacted_input,
            intent=trace.intent,
            confidence=trace.confidence,
            reason="llm_unavailable",
            agent=trace.agent,
            action_taken="escalated_to_human",
            metadata={"outcome": trace.outcome}
        ))

    # Write all records
    for record in records:
        _write_record(record)


def _write_record(record: CaseReviewRecord) -> None:
    """Append one case review record to the file."""
    CASE_REVIEW_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CASE_REVIEW_FILE.open("a") as f:
        # Convert dataclass to dict, handling the metadata field
        data = asdict(record)
        f.write(json.dumps(data) + "\n")


def read_all_records() -> list[CaseReviewRecord]:
    """Load all case review records."""
    if not CASE_REVIEW_FILE.exists():
        return []
    records = []
    with CASE_REVIEW_FILE.open("r") as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                records.append(CaseReviewRecord(**data))
    return records


def aggregate_by_category(hours: int = 24) -> dict[str, int]:
    """Count failures by category in the last N hours."""
    cutoff_ts = datetime.now().timestamp() - (hours * 3600)
    records = read_all_records()
    counts = {}
    for r in records:
        if r.ts >= cutoff_ts:
            counts[r.category] = counts.get(r.category, 0) + 1
    return counts


def get_faq_abstentions(limit: int = 50) -> list[CaseReviewRecord]:
    """Get recent FAQ abstentions (knowledge-base gaps)."""
    records = read_all_records()
    faq_cases = [r for r in records if r.category == "faq_abstain"]
    return sorted(faq_cases, key=lambda x: x.ts, reverse=True)[:limit]


def get_escalations_by_reason(limit: int = 100) -> dict[str, list[CaseReviewRecord]]:
    """Group escalations by reason."""
    records = read_all_records()
    by_reason = {}
    for r in records:
        if r.action_taken == "escalated_to_human":
            reason = r.reason
            if reason not in by_reason:
                by_reason[reason] = []
            by_reason[reason].append(r)
    # Sort each group by ts, keep recent ones
    return {k: sorted(v, key=lambda x: x.ts, reverse=True)[:limit] for k, v in by_reason.items()}


def get_summary() -> dict[str, Any]:
    """Get a high-level summary of the last 24 hours."""
    from src.logging_utils import LOG_FILE

    records = read_all_records()
    cutoff_ts = datetime.now().timestamp() - (24 * 3600)
    recent = [r for r in records if r.ts >= cutoff_ts]

    categories = {}
    for r in recent:
        categories[r.category] = categories.get(r.category, 0) + 1

    # Top failure reasons
    reasons = {}
    for r in recent:
        reasons[r.reason] = reasons.get(r.reason, 0) + 1

    # Count total messages from main event log
    total_messages_24h = 0
    if LOG_FILE.exists():
        try:
            with LOG_FILE.open("r") as f:
                for line in f:
                    try:
                        import json
                        data = json.loads(line)
                        ts = data.get("ts_start", 0)
                        if ts >= cutoff_ts:
                            total_messages_24h += 1
                    except:
                        pass
        except:
            pass

    return {
        "total_messages_24h": total_messages_24h,
        "total_reviewed_cases_24h": len(recent),  # noteworthy failures/gaps
        "by_category": categories,
        "by_reason": reasons,
        "total_cases_all_time": len(records),
    }


def clear_case_review() -> None:
    """Clear all case review records (for testing)."""
    if CASE_REVIEW_FILE.exists():
        CASE_REVIEW_FILE.unlink()
