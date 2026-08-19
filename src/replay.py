"""Replay system: run a batch of tickets through the pipeline and measure ROI.

This is the proof that improvements (e.g., adding KB docs) actually help:
- Replay N tickets before the change
- Make the change (e.g., accept a KB suggestion)
- Replay the same N tickets after the change
- Compare: cost, escalation rate, resolution rate, avg tokens
"""
from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from pathlib import Path

from src.pipeline import handle_message


@dataclass
class ReplayMetrics:
    """Stats from running a batch of tickets through the pipeline."""
    total_messages: int
    total_cost: float
    total_tokens_in: int
    total_tokens_out: int
    avg_latency_ms: float
    escalation_count: int
    resolution_by_agent: dict[str, int]  # agent -> count
    sentiment_distribution: dict[str, int]
    faq_abstain_count: int


def load_ticket_csv(path: str | Path = "customer_support_tickets.csv", limit: int | None = None) -> list[dict]:
    """Load customer tickets from CSV."""
    tickets = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if limit and i >= limit:
                break
            tickets.append(row)
    return tickets


def replay_batch(messages: list[str], channel: str = "replay", timeout_seconds: int = 120) -> ReplayMetrics:
    """Run a batch of messages through the pipeline, collect metrics."""
    import signal
    start_time = time.time()
    total_cost = 0
    total_tokens_in = 0
    total_tokens_out = 0
    total_latency_ms = 0
    escalation_count = 0
    resolution_by_agent = {}
    sentiment_distribution = {}
    faq_abstain_count = 0

    for message in messages:
        # Timeout safeguard
        if time.time() - start_time > timeout_seconds:
            break
        try:
            reply, trace = handle_message(message, channel=channel, current_user=None)

            total_cost += trace.est_cost_usd()
            total_tokens_in += trace.input_tokens
            total_tokens_out += trace.output_tokens
            total_latency_ms += (trace.latency_ms or 0)

            if trace.agent:
                resolution_by_agent[trace.agent] = resolution_by_agent.get(trace.agent, 0) + 1

            if trace.sentiment:
                sentiment_distribution[trace.sentiment] = sentiment_distribution.get(trace.sentiment, 0) + 1

            if trace.escalated or trace.agent == "handoff":
                escalation_count += 1

            # Check if FAQ abstain happened (router classified as FAQ but KB had no match)
            if trace.intent == "faq" and trace.agent == "handoff" and not trace.fallback_used:
                faq_abstain_count += 1

        except Exception as e:
            print(f"Error processing message: {e}")
            continue

    return ReplayMetrics(
        total_messages=len(messages),
        total_cost=total_cost,
        total_tokens_in=total_tokens_in,
        total_tokens_out=total_tokens_out,
        avg_latency_ms=total_latency_ms / len(messages) if messages else 0,
        escalation_count=escalation_count,
        resolution_by_agent=resolution_by_agent,
        sentiment_distribution=sentiment_distribution,
        faq_abstain_count=faq_abstain_count,
    )


def replay_csv_subset(limit: int = 100, random_seed: int = 42, timeout_seconds: int = 120) -> ReplayMetrics:
    """Replay a random sample from the CSV."""
    import random
    random.seed(random_seed)
    tickets = load_ticket_csv(limit=limit * 2)
    sample = random.sample(tickets, min(limit, len(tickets)))
    messages = [t.get("message", t.get("text", "")).strip() for t in sample if t]
    return replay_batch(messages, timeout_seconds=timeout_seconds)


def compare_metrics(before: ReplayMetrics, after: ReplayMetrics) -> dict:
    """Compare before/after metrics and compute deltas."""
    return {
        "total_messages": before.total_messages,
        "before": {
            "total_cost": round(before.total_cost, 4),
            "avg_cost_per_message": round(before.total_cost / before.total_messages, 6) if before.total_messages else 0,
            "avg_latency_ms": round(before.avg_latency_ms, 1),
            "escalation_rate": round(100 * before.escalation_count / before.total_messages, 1) if before.total_messages else 0,
            "faq_abstentions": before.faq_abstain_count,
            "total_tokens_in": before.total_tokens_in,
            "total_tokens_out": before.total_tokens_out,
        },
        "after": {
            "total_cost": round(after.total_cost, 4),
            "avg_cost_per_message": round(after.total_cost / after.total_messages, 6) if after.total_messages else 0,
            "avg_latency_ms": round(after.avg_latency_ms, 1),
            "escalation_rate": round(100 * after.escalation_count / after.total_messages, 1) if after.total_messages else 0,
            "faq_abstentions": after.faq_abstain_count,
            "total_tokens_in": after.total_tokens_in,
            "total_tokens_out": after.total_tokens_out,
        },
        "delta": {
            "cost_saved": round(before.total_cost - after.total_cost, 4),
            "cost_pct": round(100 * (before.total_cost - after.total_cost) / before.total_cost, 1) if before.total_cost > 0 else 0,
            "escalation_reduction_pct": round(100 * (before.escalation_count - after.escalation_count) / before.escalation_count, 1) if before.escalation_count > 0 else 0,
            "abstention_reduction": before.faq_abstain_count - after.faq_abstain_count,
            "avg_latency_change_ms": round(after.avg_latency_ms - before.avg_latency_ms, 1),
        }
    }
