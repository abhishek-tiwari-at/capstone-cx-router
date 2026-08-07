"""Layer 5: the LLM client wrapper with fallbacks (OpenRouter backend).

Every model call in the system goes through here so retries, timeouts, and
graceful degradation live in exactly one place. On repeated failure we do NOT
crash on a customer — we raise LLMUnavailable and the pipeline degrades to a
human handoff.

Backend: OpenRouter via the OpenAI-compatible SDK. OpenRouter does not implement
Anthropic's `messages.parse`, so structured output is done portably: we instruct
the model to emit JSON for the given schema, then validate with Pydantic. This
works across every model/provider OpenRouter routes to.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Type, TypeVar

import openai
from openai import OpenAI
from pydantic import BaseModel, ValidationError

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

_client: OpenAI | None = None
T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(RuntimeError):
    """Raised after retries are exhausted. Pipeline should fall back to human."""


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        key = os.getenv("OPENROUTER_API_KEY")
        if not key:
            raise LLMUnavailable("OPENROUTER_API_KEY is not set")
        _client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=key,
            # Optional OpenRouter attribution headers — harmless if unused.
            default_headers={
                "HTTP-Referer": "https://exl.capstone.local",
                "X-Title": "CX Micro-Intent Router",
            },
        )
    return _client


def _with_retry(fn, *, retries: int = 2, base_delay: float = 0.8):
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except (openai.RateLimitError, openai.APITimeoutError,
                openai.APIConnectionError) as e:
            last = e
            time.sleep(base_delay * (2 ** attempt))
        except openai.APIStatusError as e:
            last = e
            # Retry only on server-side errors; client errors (4xx) are terminal.
            if e.status_code and e.status_code < 500:
                break
            time.sleep(base_delay * (2 ** attempt))
    raise LLMUnavailable(str(last)) from last


def _extract_json(text: str) -> str:
    """Strip markdown fences and isolate the first JSON object in the text."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text


def _usage(resp) -> tuple[int, int]:
    u = getattr(resp, "usage", None)
    if not u:
        return 0, 0
    return getattr(u, "prompt_tokens", 0) or 0, getattr(u, "completion_tokens", 0) or 0


def parse(model: str, schema: Type[T], system: str, user: str,
          max_tokens: int = 512) -> tuple[T, int, int]:
    """Structured-output call. Returns (parsed_model, input_tokens, output_tokens)."""
    client = _get_client()
    schema_json = json.dumps(schema.model_json_schema())
    system_full = (
        f"{system}\n\nRespond with ONLY a single JSON object matching this schema. "
        f"No markdown, no code fences, no prose:\n{schema_json}"
    )

    def _call():
        return client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_full},
                {"role": "user", "content": user},
            ],
        )

    resp = _with_retry(_call)
    content = (resp.choices[0].message.content or "") if resp.choices else ""
    try:
        parsed = schema.model_validate_json(_extract_json(content))
    except (ValidationError, json.JSONDecodeError) as e:
        raise LLMUnavailable(f"structured parse failed: {e}; raw={content[:200]!r}")
    in_tok, out_tok = _usage(resp)
    return parsed, in_tok, out_tok


def complete(model: str, system: str, user: str,
             max_tokens: int = 1024) -> tuple[str, int, int]:
    """Plain text call. Returns (text, input_tokens, output_tokens)."""
    client = _get_client()

    def _call():
        return client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )

    resp = _with_retry(_call)
    text = (resp.choices[0].message.content or "") if resp.choices else ""
    in_tok, out_tok = _usage(resp)
    return text, in_tok, out_tok
