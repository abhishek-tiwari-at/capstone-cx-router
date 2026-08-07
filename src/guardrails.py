"""Layer 1 & 4: input and output guardrails.

Enterprise concerns handled here:
  - PII redaction (compliance / DPDP Act 2023, GDPR) before anything is logged.
  - Prompt-injection / abuse detection on the way in.
  - Output validation on the way out (no fabricated financial promises, basic
    toxicity gate).

These are deliberately lightweight, regex-first checks. In production you'd swap
the detectors for a dedicated PII service and a moderation model — the interface
stays the same. That "thin real slice + clear upgrade path" is the pitch.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- PII patterns -----------------------------------------------------------
_PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("PHONE", re.compile(r"\b(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{3}\)?[\s-]?)\d{3}[\s-]?\d{4}\b")),
    ("CARD", re.compile(r"\b(?:\d[ -]*?){13,16}\b")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("ZIP", re.compile(r"\bzip\s*(?:code)?\s*(?:is)?[:\s]*\d{5}\b", re.IGNORECASE)),
]

_INJECTION_MARKERS = [
    "ignore previous instructions", "ignore the above", "disregard your",
    "you are now", "system prompt", "reveal your instructions", "jailbreak",
]

# Words a bot must never assert without a confirmed backend action.
_UNSAFE_OUTPUT_PROMISES = [
    "i have refunded", "your refund has been processed", "i have cancelled",
    "your account is now closed", "i have credited",
]


def redact_pii(text: str) -> str:
    """Replace PII spans with typed placeholders, e.g. [EMAIL]. Safe for logs."""
    redacted = text
    for label, pattern in _PII_PATTERNS:
        redacted = pattern.sub(f"[{label}]", redacted)
    return redacted


@dataclass
class InputCheck:
    allowed: bool
    reason: str = ""
    flags: list[str] = field(default_factory=list)


def check_input(text: str) -> InputCheck:
    """Input guardrail. Blocks obvious prompt-injection / abuse attempts."""
    lowered = text.lower()
    flags = [m for m in _INJECTION_MARKERS if m in lowered]
    if flags:
        return InputCheck(allowed=False, reason="possible_prompt_injection", flags=flags)
    if not text.strip():
        return InputCheck(allowed=False, reason="empty_message")
    return InputCheck(allowed=True)


@dataclass
class OutputCheck:
    safe: bool
    reason: str = ""


def check_output(text: str) -> OutputCheck:
    """Output guardrail. Blocks responses that claim a financial action was taken
    (those must come from the transaction backend + human-in-the-loop, never the
    language model alone)."""
    lowered = text.lower()
    for promise in _UNSAFE_OUTPUT_PROMISES:
        if promise in lowered:
            return OutputCheck(safe=False, reason=f"unverified_promise:{promise}")
    return OutputCheck(safe=True)
