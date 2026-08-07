"""Seed a labeled test set from the raw ticket CSV.

Samples N tickets per ticket type, cleans the template placeholders, and maps
ticket type -> a candidate router intent (config.TICKET_TYPE_TO_INTENT). The
`label` column is a STARTING POINT — Day 1 task is for the team to hand-correct
it, especially adding empathy/handoff cases that ticket type alone can't capture.

Run:  python eval/build_testset.py --per-type 12
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from config import SOURCE_CSV, TESTSET, TICKET_TYPE_TO_INTENT


def clean(text: str) -> str:
    if not isinstance(text, str):
        return ""
    # Strip the dataset's template placeholder and collapse whitespace.
    text = text.replace("{product_purchased}", "the product")
    return " ".join(text.split())[:500]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-type", type=int, default=12)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    df = pd.read_csv(SOURCE_CSV)
    rows = []
    for ttype, group in df.groupby("Ticket Type"):
        sample = group.sample(min(args.per_type, len(group)), random_state=args.seed)
        for _, r in sample.iterrows():
            rows.append({
                "ticket_id": r["Ticket ID"],
                "ticket_type": ttype,
                "priority": r["Ticket Priority"],
                "message": clean(r["Ticket Description"]),
                "label": TICKET_TYPE_TO_INTENT.get(ttype, "handoff"),
                "label_confirmed": False,  # flip to True after human review
            })

    out = pd.DataFrame(rows)
    TESTSET.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(TESTSET, index=False)
    print(f"Wrote {len(out)} seed rows -> {TESTSET}")
    print("NEXT: open it, correct `label`, add empathy/handoff cases, set "
          "label_confirmed=True. That labeled set is every number in your pitch.")


if __name__ == "__main__":
    main()
