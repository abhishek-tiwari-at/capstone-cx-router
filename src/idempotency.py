"""Idempotency store — suppress duplicate transaction requests.

Without this, a retry, a double-click, or a customer re-asking would propose the
same refund twice. We derive a stable key from the request and remember the
decision for a TTL window; a repeat within that window returns the original
decision instead of creating a new action.

Backed by a small JSON file — fine for the demo. At scale this becomes a
client-supplied `Idempotency-Key` header (Stripe-style) backed by Redis/DB.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from config import IDEMPOTENCY_STORE, IDEMPOTENCY_TTL_HOURS


def make_key(action: str, order_reference: str | None, amount: float | None,
             message: str) -> str:
    """Stable key for a logical request. Uses order reference when available,
    otherwise falls back to the normalized message text."""
    basis = f"{action}|{order_reference or message.strip().lower()}|{amount}"
    return hashlib.sha256(basis.encode()).hexdigest()[:16]


def _load() -> dict[str, Any]:
    if not IDEMPOTENCY_STORE.exists():
        return {}
    try:
        return json.loads(IDEMPOTENCY_STORE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save(store: dict[str, Any]) -> None:
    IDEMPOTENCY_STORE.parent.mkdir(parents=True, exist_ok=True)
    IDEMPOTENCY_STORE.write_text(json.dumps(store, indent=2))


def check_and_record(key: str, decision: dict[str, Any]) -> tuple[bool, dict | None]:
    """Return (is_duplicate, original_record). Records the decision on first sight
    and purges entries older than the TTL."""
    now = time.time()
    ttl = IDEMPOTENCY_TTL_HOURS * 3600
    store = {k: v for k, v in _load().items() if now - v.get("ts", 0) < ttl}

    if key in store:
        return True, store[key]

    store[key] = {"decision": decision, "ts": now}
    _save(store)
    return False, None
