"""Layer 3 (grounding): the RAG retriever for the FAQ agent.

Local, dependency-light vector store: sentence-transformers embeddings + in-memory
cosine similarity. Deliberately behind a small interface (VectorStore) so we can
swap in a managed vector DB later without touching the FAQ agent — that migration
path is part of the enterprise story.

The FAQ agent answers ONLY from retrieved context and abstains when nothing is
relevant. That abstain-on-no-match behavior is the anti-hallucination guarantee.
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass

import numpy as np

from config import KB_DIR, KB_INDEX

_EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
# Below this cosine similarity we treat retrieval as "no relevant doc found".
RELEVANCE_FLOOR = 0.30

_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer(_EMBED_MODEL_NAME)
    return _embedder


def embed(texts: list[str]) -> np.ndarray:
    vecs = _get_embedder().encode(texts, normalize_embeddings=True)
    return np.asarray(vecs, dtype=np.float32)


@dataclass
class Doc:
    source: str
    text: str


@dataclass
class Retrieved:
    doc: Doc
    score: float


class VectorStore:
    """In-memory cosine store. Same shape a managed DB adapter would expose."""

    def __init__(self, docs: list[Doc], matrix: np.ndarray):
        self.docs = docs
        self.matrix = matrix  # (N, dim), L2-normalized

    def search(self, query: str, k: int = 3) -> list[Retrieved]:
        q = embed([query])[0]
        scores = self.matrix @ q
        top = np.argsort(scores)[::-1][:k]
        return [Retrieved(self.docs[i], float(scores[i])) for i in top]

    def save(self) -> None:
        KB_INDEX.parent.mkdir(parents=True, exist_ok=True)
        with KB_INDEX.open("wb") as f:
            pickle.dump({"docs": self.docs, "matrix": self.matrix}, f)

    @classmethod
    def load(cls) -> "VectorStore":
        with KB_INDEX.open("rb") as f:
            blob = pickle.load(f)
        return cls(blob["docs"], blob["matrix"])


def build_index_from_kb() -> VectorStore:
    """Read every .md file in KB_DIR, embed, and persist the index."""
    docs: list[Doc] = []
    for path in sorted(KB_DIR.glob("*.md")):
        docs.append(Doc(source=path.name, text=path.read_text().strip()))
    if not docs:
        raise RuntimeError(f"No knowledge-base docs found in {KB_DIR}")
    store = VectorStore(docs, embed([d.text for d in docs]))
    store.save()
    return store
