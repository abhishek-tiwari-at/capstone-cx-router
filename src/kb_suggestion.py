"""KB suggestion system: surfaces knowledge-base gaps and enables humans to patch them.

When the FAQ agent abstains (no match above relevance floor), we log the customer
query as a gap. This module:

1. Aggregates recent FAQ abstentions
2. Extracts key phrases and topics
3. Generates a suggested KB doc template
4. Allows human to write the answer and save it
5. Re-indexes the KB and re-runs the pipeline to measure impact
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import re

from src import case_review, rag

SUGGESTIONS_FILE = Path("data/kb_suggestions.jsonl")
KB_DIR = Path("data/knowledge_base")


@dataclass
class KBSuggestion:
    """A suggested KB entry, derived from a failed FAQ query."""
    suggestion_id: str
    query: str  # the customer's original question
    trace_ids: list[str]  # traces that triggered this suggestion
    suggested_title: str
    suggested_structure: str  # template/skeleton
    human_answer: str | None = None  # filled in by a human
    status: str = "pending"  # pending | accepted | rejected | archived
    impact_before: dict | None = None
    impact_after: dict | None = None


def extract_key_phrases(text: str) -> list[str]:
    """Extract nouns/key phrases from a query."""
    # Very simple: split on spaces, take words > 3 chars, exclude common stop words
    stop = {"the", "a", "an", "and", "or", "is", "are", "how", "what", "when", "where", "why"}
    words = text.lower().split()
    return [w for w in words if len(w) > 3 and w not in stop and re.match(r"[a-z]+", w)]


def generate_suggestion_template(query: str, key_phrases: list[str]) -> str:
    """Generate a KB doc skeleton based on the query."""
    phrases_str = ", ".join(key_phrases[:5]) if key_phrases else query
    return f"""
**Q: {query}**

**A:** [Please write the answer here based on company policy/knowledge]

**Related topics:** {phrases_str}

**Last updated:** [auto-filled on save]
"""


def get_suggestion_id(query: str, ts: float) -> str:
    """Generate a unique ID for a suggestion."""
    import hashlib
    combined = f"{query}:{ts}".encode()
    return "sugg_" + hashlib.md5(combined).hexdigest()[:8]


def suggest_from_case_review() -> list[KBSuggestion]:
    """Extract recent FAQ abstentions and generate suggestions."""
    from datetime import datetime
    abstentions = case_review.get_faq_abstentions(limit=100)

    suggestions = []
    seen_queries = set()

    for abstention in abstentions:
        query = abstention.message.strip()
        if not query or query in seen_queries:
            continue
        seen_queries.add(query)

        key_phrases = extract_key_phrases(query)
        suggested_title = f"Q: {query[:50]}"
        skeleton = generate_suggestion_template(query, key_phrases)

        suggestion_id = get_suggestion_id(query, abstention.ts)
        sugg = KBSuggestion(
            suggestion_id=suggestion_id,
            query=query,
            trace_ids=[abstention.trace_id],
            suggested_title=suggested_title,
            suggested_structure=skeleton,
        )
        suggestions.append(sugg)

    return suggestions


def save_human_answer(suggestion_id: str, answer: str) -> None:
    """Record that a human has answered a suggestion."""
    suggestions = read_suggestions()
    for s in suggestions:
        if s.suggestion_id == suggestion_id:
            s.human_answer = answer
            s.status = "answered"
            break
    _write_suggestions(suggestions)


def accept_suggestion(suggestion_id: str, kb_content: str, vertical: str = "ecommerce") -> str:
    """Accept a suggestion: save it as a KB doc and return the filename."""
    from src import verticals
    suggestions = read_suggestions()
    suggestion = None
    for s in suggestions:
        if s.suggestion_id == suggestion_id:
            suggestion = s
            break

    if not suggestion:
        raise ValueError(f"Suggestion {suggestion_id} not found")

    # Save as a new KB doc in the vertical's KB dir
    vc = verticals.get_vertical(vertical)
    kb_dir = vc.kb_path
    kb_dir.mkdir(parents=True, exist_ok=True)
    filename = f"user_added_{suggestion_id}.md"
    filepath = kb_dir / filename
    filepath.write_text(kb_content)

    suggestion.status = "accepted"
    _write_suggestions(suggestions)

    # Re-index the vertical's KB
    rag.build_index_from_kb(vertical=vertical)

    return filename


def read_suggestions() -> list[KBSuggestion]:
    """Load all KB suggestions."""
    if not SUGGESTIONS_FILE.exists():
        return []
    suggestions = []
    with SUGGESTIONS_FILE.open("r") as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                suggestions.append(KBSuggestion(**data))
    return suggestions


def _write_suggestions(suggestions: list[KBSuggestion]) -> None:
    """Write suggestions to file."""
    SUGGESTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SUGGESTIONS_FILE.open("w") as f:
        for s in suggestions:
            data = {
                "suggestion_id": s.suggestion_id,
                "query": s.query,
                "trace_ids": s.trace_ids,
                "suggested_title": s.suggested_title,
                "suggested_structure": s.suggested_structure,
                "human_answer": s.human_answer,
                "status": s.status,
            }
            f.write(json.dumps(data) + "\n")


def get_pending_suggestions() -> list[KBSuggestion]:
    """Get suggestions waiting for human action."""
    return [s for s in read_suggestions() if s.status == "pending"]


def get_accepted_suggestions() -> list[KBSuggestion]:
    """Get suggestions that have been accepted and added to KB."""
    return [s for s in read_suggestions() if s.status == "accepted"]
