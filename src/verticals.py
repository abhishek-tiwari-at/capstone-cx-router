"""Multi-vertical support: prove scalability across industries.

Same router, different configs. Each vertical has:
- Taxonomy (intents)
- Policy thresholds
- Knowledge base
- Sample test cases

Verticals: e-commerce (current), banking, telecom.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class VerticalConfig:
    """Configuration for a specific industry vertical."""
    name: str
    display_name: str
    description: str
    kb_path: Path
    confidence_threshold: float
    sentiment_intensity_threshold: float
    auto_approve_limit: int  # different per vertical
    test_cases: list[dict]


# E-Commerce vertical (current)
ECOMMERCE = VerticalConfig(
    name="ecommerce",
    display_name="E-Commerce",
    description="Retail & order fulfillment",
    kb_path=Path("data/knowledge_base"),
    confidence_threshold=0.75,
    sentiment_intensity_threshold=0.8,
    auto_approve_limit=2000,
    test_cases=[
        {
            "message": "When will my order arrive?",
            "expected_agent": "faq",
            "user": "Priya",
        },
        {
            "message": "Refund ORD-1001",
            "expected_agent": "transaction",
            "user": "Priya",
        },
        {
            "message": "This is unacceptable!",
            "expected_agent": "handoff",
            "user": "Priya",
        },
    ]
)

# Banking vertical
BANKING = VerticalConfig(
    name="banking",
    display_name="Banking & Finance",
    description="Accounts, transfers, compliance",
    kb_path=Path("data/knowledge_base_banking"),
    confidence_threshold=0.85,  # higher threshold for finance
    sentiment_intensity_threshold=0.8,
    auto_approve_limit=1000,  # lower limit for transfers
    test_cases=[
        {
            "message": "How do I check my balance?",
            "expected_agent": "faq",
            "user": "Alice",
        },
        {
            "message": "Transfer $500 to savings",
            "expected_agent": "transaction",
            "user": "Alice",
        },
        {
            "message": "I'm missing a transaction",
            "expected_agent": "empathy",  # needs human touch
            "user": "Alice",
        },
    ]
)

# Telecom vertical
TELECOM = VerticalConfig(
    name="telecom",
    display_name="Telecom & Mobile",
    description="Plans, billing, connectivity",
    kb_path=Path("data/knowledge_base_telecom"),
    confidence_threshold=0.70,  # lower threshold for telco (more variation)
    sentiment_intensity_threshold=0.75,
    auto_approve_limit=500,  # very low auto-approve for billing
    test_cases=[
        {
            "message": "What is my plan?",
            "expected_agent": "faq",
            "user": "Bob",
        },
        {
            "message": "I was overcharged this month",
            "expected_agent": "transaction",
            "user": "Bob",
        },
        {
            "message": "I'm switching providers",
            "expected_agent": "handoff",  # churn risk
            "user": "Bob",
        },
    ]
)

VERTICALS = {
    "ecommerce": ECOMMERCE,
    "banking": BANKING,
    "telecom": TELECOM,
}


def get_vertical(name: str) -> VerticalConfig | None:
    """Get a vertical by name."""
    return VERTICALS.get(name)


def list_verticals() -> list[dict]:
    """List all available verticals."""
    return [
        {
            "name": v.name,
            "display_name": v.display_name,
            "description": v.description,
        }
        for v in VERTICALS.values()
    ]


def get_vertical_summary(name: str) -> dict | None:
    """Get summary info about a vertical."""
    v = get_vertical(name)
    if not v:
        return None
    return {
        "name": v.name,
        "display_name": v.display_name,
        "description": v.description,
        "confidence_threshold": v.confidence_threshold,
        "sentiment_intensity_threshold": v.sentiment_intensity_threshold,
        "auto_approve_limit": v.auto_approve_limit,
        "sample_test_cases": len(v.test_cases),
    }
