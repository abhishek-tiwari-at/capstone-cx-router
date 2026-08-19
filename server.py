"""Web backend for the chat dashboard.

    pip install fastapi "uvicorn[standard]"
    uvicorn server:app --port 8000
    # open http://localhost:8000

Serves the single-page dashboard and exposes:
  GET  /api/users            -> order owners (for the "logged in as" selector)
  GET  /api/orders?owner=..  -> that owner's orders (shown in the UI)
  POST /api/chat             -> run one message through the full pipeline, return
                                the reply AND the decision trace for the side panel
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src import orders, case_review, kb_suggestion, replay, governance, verticals
from src.pipeline import handle_message

app = FastAPI(title="CX Micro-Intent Router")
WEB = Path(__file__).parent / "web"


class ChatIn(BaseModel):
    message: str
    user: str | None = None
    vertical: str = "ecommerce"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


@app.get("/api/users")
def users() -> list[dict]:
    return orders.owners()


@app.get("/api/orders")
def orders_for(owner: str) -> list[dict]:
    return orders.for_owner(owner)


@app.post("/api/chat")
def chat(inp: ChatIn) -> dict:
    reply, tr = handle_message(inp.message, channel="web", current_user=inp.user, vertical=inp.vertical)
    return {
        "reply": reply,
        "intent": tr.intent,
        "confidence": tr.confidence,
        "sentiment": tr.sentiment,
        "sentiment_intensity": tr.sentiment_intensity,
        "churn_risk": tr.churn_risk,
        "agent": tr.agent,
        "escalated": tr.escalated,
        "outcome": tr.outcome,
        "router_reason": tr.router_reason,
        "guardrail_blocks": tr.guardrail_blocks,
        "fallback_used": tr.fallback_used,
        "latency_ms": tr.latency_ms,
        "cost": tr.est_cost_usd(),
    }


@app.get("/api/case-review/summary")
def case_review_summary() -> dict:
    return case_review.get_summary()


@app.get("/api/case-review/faq-abstentions")
def faq_abstentions(limit: int = 50) -> list[dict]:
    records = case_review.get_faq_abstentions(limit=limit)
    return [
        {
            "trace_id": r.trace_id,
            "ts": r.ts,
            "actor": r.actor,
            "message": r.message,
            "intent": r.intent,
            "reason": r.reason,
        }
        for r in records
    ]


@app.get("/api/case-review/escalations")
def escalations_by_reason() -> dict:
    data = case_review.get_escalations_by_reason()
    return {
        reason: [
            {
                "trace_id": r.trace_id,
                "ts": r.ts,
                "actor": r.actor,
                "message": r.message,
                "confidence": r.confidence,
            }
            for r in records
        ]
        for reason, records in data.items()
    }


@app.get("/api/kb-suggestions/pending")
def kb_suggestions_pending() -> list[dict]:
    suggestions = kb_suggestion.get_pending_suggestions()
    return [
        {
            "suggestion_id": s.suggestion_id,
            "query": s.query,
            "suggested_title": s.suggested_title,
            "suggested_structure": s.suggested_structure,
            "status": s.status,
        }
        for s in suggestions
    ]


class KBAnswerIn(BaseModel):
    suggestion_id: str
    kb_content: str
    vertical: str = "ecommerce"


@app.post("/api/kb-suggestions/accept")
def accept_kb_suggestion(inp: KBAnswerIn) -> dict:
    try:
        filename = kb_suggestion.accept_suggestion(inp.suggestion_id, inp.kb_content, vertical=inp.vertical)
        return {"status": "accepted", "filename": filename}
    except Exception as e:
        return {"status": "error", "reason": str(e)}


@app.post("/api/kb-suggestions/refresh")
def refresh_kb_suggestions() -> dict:
    """Generate fresh suggestions from recent case review data."""
    suggestions = kb_suggestion.suggest_from_case_review()
    return {
        "count": len(suggestions),
        "suggestions": [
            {
                "suggestion_id": s.suggestion_id,
                "query": s.query,
                "status": s.status,
            }
            for s in suggestions
        ]
    }


@app.post("/api/replay/quick")
def replay_quick(limit: int = 10) -> dict:
    """Run a quick replay of N tickets for ROI demo."""
    metrics = replay.replay_csv_subset(limit=limit)
    return {
        "messages_processed": metrics.total_messages,
        "total_cost": round(metrics.total_cost, 4),
        "avg_cost_per_message": round(metrics.total_cost / metrics.total_messages, 6),
        "avg_latency_ms": round(metrics.avg_latency_ms, 1),
        "escalation_count": metrics.escalation_count,
        "escalation_rate": round(100 * metrics.escalation_count / metrics.total_messages, 1),
        "faq_abstentions": metrics.faq_abstain_count,
        "total_tokens_in": metrics.total_tokens_in,
        "total_tokens_out": metrics.total_tokens_out,
        "resolution_by_agent": metrics.resolution_by_agent,
        "sentiment_distribution": metrics.sentiment_distribution,
    }


@app.get("/api/governance/policy")
def governance_policy() -> dict:
    """Get current policy settings."""
    policy = governance.get_current_policy()
    return {
        "confidence_threshold": policy.confidence_threshold,
        "sentiment_intensity_threshold": policy.sentiment_intensity_threshold,
        "auto_approve_limit": policy.auto_approve_limit,
    }


@app.post("/api/governance/red-team")
def governance_red_team() -> dict:
    """Run red-team test suite."""
    return governance.get_red_team_summary()


@app.get("/api/verticals")
def list_verticals_endpoint() -> list[dict]:
    """List available verticals (industries)."""
    return verticals.list_verticals()


@app.get("/api/verticals/{name}")
def get_vertical_endpoint(name: str) -> dict | None:
    """Get summary of a specific vertical."""
    return verticals.get_vertical_summary(name)
