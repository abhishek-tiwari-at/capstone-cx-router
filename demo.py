"""Presentation demo runner — the whole thesis in five messages.

Two modes so the live demo never stalls on the ~8s brain:

    python demo.py          # run live through the real pipeline, cache results
    python demo.py --replay # print cached results INSTANTLY (no API calls)

Run it once live before presenting, then present with --replay.

Each scenario maps to one pillar of the pitch:
  1. FAQ         -> RAG grounding + citation (no hallucination)
  2. Empathy     -> tone de-escalation, no false promises
  3. Transaction -> human-in-the-loop money gate (bot never moves money)
  4. Ambiguous   -> low confidence -> human handoff + escalation brief
  5. Churn risk  -> a furious customer is fast-tracked to a human on sentiment
"""
from __future__ import annotations

import json
import sys

from config import DATA_DIR

CACHE = DATA_DIR / "demo_cache.json"

SCENARIOS: list[tuple[str, str]] = [
    ("FAQ · grounded answer",
     "How long does a refund usually take to show up on my card?"),
    ("EMPATHY · de-escalation",
     "This is the third time I've contacted you and nobody has helped me. "
     "I'm honestly done with this."),
    ("TRANSACTION · human-in-the-loop",
     "Please cancel my subscription and refund the last payment."),
    ("SAFETY · low confidence -> human handoff",
     "idk it's just the thing isn't right, you know? can someone sort it"),
    ("CHURN RISK · sentiment fast-track",
     "This is absolutely unacceptable. I've wasted my whole day, your service is "
     "garbage, and I am cancelling everything and switching to a competitor TODAY."),
]


def _card(label: str, message: str, d: dict) -> None:
    bar = "─" * 72
    print(f"\n{bar}\n▶ {label}")
    print(f"  customer : {message}")
    print(f"  sentiment: {d.get('sentiment')} ({d.get('sentiment_intensity')})"
          + ("   ⚠ CHURN RISK" if d.get("churn_risk") else ""))
    print(f"  routed   : {d['intent']}   conf={d['confidence']}   "
          f"escalated={d['escalated']}")
    if d.get("router_reason"):
        print(f"  reason   : {d['router_reason']}")
    print(f"  agent    : {d['agent']}   outcome={d['outcome']}")
    print(f"  metrics  : latency={d['latency_ms']}ms   cost=${d['cost']:.5f}")
    print(f"\n  BOT: {d['reply']}")


def run_live() -> list[dict]:
    from src.pipeline import handle_message
    results = []
    for label, message in SCENARIOS:
        print(f"  … running: {label}")
        reply, tr = handle_message(message, channel="demo")
        results.append({
            "label": label, "message": message,
            "intent": tr.intent, "confidence": tr.confidence,
            "sentiment": tr.sentiment, "sentiment_intensity": tr.sentiment_intensity,
            "churn_risk": tr.churn_risk,
            "escalated": tr.escalated, "agent": tr.agent,
            "outcome": tr.outcome, "router_reason": tr.router_reason,
            "latency_ms": tr.latency_ms, "cost": tr.est_cost_usd(),
            "reply": reply,
        })
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(results, indent=2))
    print(f"\n  cached -> {CACHE}")
    return results


def main() -> None:
    replay = "--replay" in sys.argv
    if replay:
        if not CACHE.exists():
            print("No cache yet. Run `python demo.py` once (live) first.")
            return
        results = json.loads(CACHE.read_text())
    else:
        results = run_live()

    print("\n" + "=" * 72)
    print("  CX MICRO-INTENT ROUTER  —  the triage nurse before the bot")
    print("=" * 72)
    for r in results:
        _card(r["label"], r["message"], r)
    print("\n" + "=" * 72)
    total = sum(r["cost"] for r in results)
    esc = sum(1 for r in results if r["escalated"])
    churn = sum(1 for r in results if r.get("churn_risk"))
    print(f"  {len(results)} messages · {esc} safely escalated · "
          f"{churn} churn-risk caught · total cost ${total:.5f}")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()
