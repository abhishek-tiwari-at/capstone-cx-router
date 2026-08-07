"""Build the RAG index from the knowledge-base markdown files.

Run once (and after editing any KB doc):
    python scripts/build_kb.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import KB_DIR, KB_INDEX
from src import rag


def main() -> None:
    store = rag.build_index_from_kb()
    print(f"Indexed {len(store.docs)} docs from {KB_DIR}")
    print(f"Saved index -> {KB_INDEX}")


if __name__ == "__main__":
    main()
