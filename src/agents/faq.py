"""FAQ agent — RAG-grounded, cites sources, abstains when unsure.

This is the grounding story: it retrieves from the knowledge base and answers
ONLY from that context. If nothing clears the relevance floor, it does not
hallucinate — it says so and the pipeline escalates.
"""
from __future__ import annotations

from config import AGENT_MODEL
from src import llm, rag
from src.logging_utils import Trace

_SYSTEM = (
    "You are a factual FAQ assistant. Answer the customer's question using ONLY "
    "the provided knowledge-base context. If the context does not contain the "
    "answer, reply exactly: 'INSUFFICIENT_CONTEXT'. Never use outside knowledge. "
    "Cite the source filename(s) you used in square brackets at the end."
)

_store: rag.VectorStore | None = None


def _get_store() -> rag.VectorStore:
    global _store
    if _store is None:
        _store = rag.VectorStore.load()
    return _store


def handle(message: str, trace: Trace) -> str:
    hits = _get_store().search(message, k=3)
    relevant = [h for h in hits if h.score >= rag.RELEVANCE_FLOOR]

    if not relevant:
        # Grounding guarantee: no relevant doc -> abstain, don't invent.
        raise AbstainError("no knowledge-base match above relevance floor")

    context = "\n\n".join(f"[{h.doc.source}] {h.doc.text}" for h in relevant)
    user = f"Knowledge base context:\n{context}\n\nCustomer question: {message}"
    answer, in_tok, out_tok = llm.complete(AGENT_MODEL, _SYSTEM, user, max_tokens=600)
    trace.input_tokens += in_tok
    trace.output_tokens += out_tok

    if "INSUFFICIENT_CONTEXT" in answer:
        raise AbstainError("model judged context insufficient")
    return answer


class AbstainError(RuntimeError):
    """FAQ could not answer from grounded context; pipeline should escalate."""
