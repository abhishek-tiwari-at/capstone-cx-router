"""Order store — the system-of-record the transaction agent grounds on.

Gives the bot real order facts (id, description, value, owner) so that:
  - the refund AMOUNT comes from the order's real value, not the customer's claim
    (that authoritative amount feeds the $2k policy engine);
  - actions can be tied to an OWNER, so we can verify the requester actually owns
    the order (access control — prevents acting on someone else's order).

Backed by a JSON file for the demo; a real system swaps this for a DB/API behind
the same interface.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from config import DATA_DIR

ORDERS_FILE = DATA_DIR / "orders.json"

_orders: dict[str, "Order"] = {}


@dataclass
class Order:
    order_id: str
    description: str
    value: float
    owner_name: str
    owner_email: str

    def as_dict(self) -> dict:
        return asdict(self)


def _load() -> dict[str, Order]:
    global _orders
    if not _orders:
        data = json.loads(ORDERS_FILE.read_text())
        _orders = {o["order_id"]: Order(**o) for o in data["orders"]}
    return _orders


def get(order_reference: str | None) -> Order | None:
    """Look up an order, tolerating '1001' / 'ord-1001' / 'ORD-1001'."""
    if not order_reference:
        return None
    key = order_reference.strip().upper()
    store = _load()
    if key in store:
        return store[key]
    if not key.startswith("ORD-") and f"ORD-{key}" in store:
        return store[f"ORD-{key}"]
    return None


def owns(order_id: str, email: str | None) -> bool:
    order = _load().get(order_id)
    if not order or not email:
        return False
    return order.owner_email.lower() == email.strip().lower()


def for_owner(email: str) -> list[dict]:
    return [o.as_dict() for o in _load().values()
            if o.owner_email.lower() == email.strip().lower()]


def owners() -> list[dict]:
    seen: dict[str, str] = {}
    for o in _load().values():
        seen[o.owner_email] = o.owner_name
    return [{"name": n, "email": e} for e, n in seen.items()]
