"""Pretty-print the audit log (data/events.jsonl).

    python view_logs.py         # last 15 decisions
    python view_logs.py 40      # last 40

Each line is one governed decision: who asked, how it was routed, whether it
escalated, cost, and the outcome. PII is already redacted in the stored records.
"""
import datetime
import json
import sys

from config import LOG_FILE


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    if not LOG_FILE.exists():
        print("No logs yet — send a message first.")
        return

    lines = LOG_FILE.read_text().splitlines()[-n:]
    hdr = (f"{'time':19}  {'actor':18}  {'intent':10}  {'sentiment':11}  "
           f"esc  churn  {'cost':9}  outcome")
    print(hdr)
    print("-" * len(hdr))
    for ln in lines:
        r = json.loads(ln)
        ts = datetime.datetime.fromtimestamp(r.get("ts_start", 0)).strftime("%Y-%m-%d %H:%M:%S")
        senti = str(r.get("sentiment") or "-")
        if r.get("sentiment_intensity") is not None:
            senti = f"{senti}·{r['sentiment_intensity']:.1f}"
        print(f"{ts:19}  {str(r.get('actor') or '-')[:18]:18}  "
              f"{str(r.get('intent') or '-')[:10]:10}  {senti[:11]:11}  "
              f"{str(r.get('escalated'))[:4]:4} {'YES' if r.get('churn_risk') else '-':5}  "
              f"${r.get('est_cost_usd', 0):.5f}  {str(r.get('outcome') or '')[:55]}")


if __name__ == "__main__":
    main()
