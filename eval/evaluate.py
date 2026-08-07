"""Evaluate the router against the labeled test set.

Prints overall accuracy, a confusion matrix, and the escalation rate — the exact
numbers for the trainer pitch. Only rows with label_confirmed=True are scored, so
un-reviewed seed labels don't pollute your metrics.

Run:  python eval/evaluate.py
"""
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from config import INTENTS, TESTSET
from src.router import route


def main() -> None:
    df = pd.read_csv(TESTSET)
    if "label_confirmed" in df.columns:
        reviewed = df[df["label_confirmed"] == True]  # noqa: E712
        if len(reviewed) == 0:
            print("No confirmed labels yet — scoring ALL seed rows (noisy).")
            print("Confirm labels in the test set for trustworthy numbers.\n")
        else:
            df = reviewed

    labels = list(INTENTS)
    confusion = defaultdict(Counter)
    correct = 0
    escalations = 0

    for _, row in df.iterrows():
        gold = row["label"]
        try:
            decision, _, _ = route(str(row["message"]))
            pred = decision.intent
        except Exception as e:  # noqa: BLE001
            pred = "handoff"  # a routing failure degrades to handoff by design
            print(f"  [warn] routing error on ticket {row.get('ticket_id')}: {e}")
        confusion[gold][pred] += 1
        correct += int(pred == gold)
        escalations += int(pred == "handoff")

    n = len(df)
    print(f"\nRouter accuracy: {correct}/{n} = {correct / n:.1%}")
    print(f"Escalation rate: {escalations}/{n} = {escalations / n:.1%}\n")

    header = "gold \\ pred".ljust(14) + "".join(l[:8].ljust(9) for l in labels)
    print(header)
    for gold in labels:
        line = gold.ljust(14) + "".join(str(confusion[gold][p]).ljust(9) for p in labels)
        print(line)


if __name__ == "__main__":
    main()
