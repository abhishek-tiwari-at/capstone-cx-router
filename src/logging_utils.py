"""Layer 6: structured observability.

Every message produces one JSON trace line: trace_id, timestamps, the routing
decision (intent + confidence + reason), which agent handled it, latency, token
usage, cost, and outcome. This is the "outcome feeds back" loop from the
architecture diagram, made concrete — and it's your metrics source for the demo.

All logged text is PII-redacted at the call site (see guardrails.redact_pii),
so this file never has to worry about secrets landing on disk.
"""
from __future__ import annotations

import json
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any

from config import LOG_FILE


def new_trace_id() -> str:
    return f"trace_{uuid.uuid4().hex[:12]}"


@dataclass
class Trace:
    trace_id: str = field(default_factory=new_trace_id)
    ts_start: float = field(default_factory=time.time)
    channel: str = "cli"
    actor: str | None = None          # authenticated requester (who acted)
    redacted_input: str = ""
    intent: str | None = None
    confidence: float | None = None
    router_reason: str | None = None
    sentiment: str | None = None
    sentiment_intensity: float | None = None
    churn_risk: bool = False
    agent: str | None = None
    escalated: bool = False
    fallback_used: bool = False
    guardrail_blocks: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float | None = None
    outcome: str | None = None
    redacted_response: str = ""

    # Rough blended cost estimate (USD) for the pitch's cost story. Tune per model.
    def est_cost_usd(self) -> float:
        # Haiku+Sonnet blended ballpark: $3/1M in, $15/1M out.
        return round(self.input_tokens * 3e-6 + self.output_tokens * 15e-6, 6)

    def finish(self, outcome: str) -> None:
        self.outcome = outcome
        self.latency_ms = round((time.time() - self.ts_start) * 1000, 1)

    def write(self) -> None:
        record: dict[str, Any] = asdict(self)
        record["est_cost_usd"] = self.est_cost_usd()
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a") as f:
            f.write(json.dumps(record) + "\n")


@contextmanager
def trace_scope(channel: str = "cli"):
    """Convenience context manager: yields a Trace, always writes it on exit."""
    tr = Trace(channel=channel)
    try:
        yield tr
    finally:
        if tr.outcome is None:
            tr.finish("error")
        elif tr.latency_ms is None:
            # Agent set outcome directly (e.g. transaction) and skipped finish();
            # stamp latency here so every trace always has it.
            tr.latency_ms = round((time.time() - tr.ts_start) * 1000, 1)
        tr.write()
