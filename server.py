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

from src import orders
from src.pipeline import handle_message

app = FastAPI(title="CX Micro-Intent Router")
WEB = Path(__file__).parent / "web"


class ChatIn(BaseModel):
    message: str
    user: str | None = None


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
    reply, tr = handle_message(inp.message, channel="web", current_user=inp.user)
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
