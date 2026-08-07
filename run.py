"""Interactive CLI demo — the end-to-end pipeline in one screen.

    python run.py                 # interactive chat loop
    python run.py "your message"  # single message

Shows the routing decision (intent + confidence + reason) alongside the reply,
which is exactly what you want visible during the live trainer demo.
"""
import sys

from src.pipeline import handle_message


def show(message: str) -> None:
    reply, trace = handle_message(message)
    print(f"\n  routed -> {trace.intent}  (conf={trace.confidence}, "
          f"agent={trace.agent}, escalated={trace.escalated})")
    if trace.router_reason:
        print(f"  reason -> {trace.router_reason}")
    print(f"  latency={trace.latency_ms}ms  cost=${trace.est_cost_usd():.5f}  "
          f"outcome={trace.outcome}")
    print(f"\nBOT: {reply}\n")


def main() -> None:
    if len(sys.argv) > 1:
        show(" ".join(sys.argv[1:]))
        return
    print("CX Micro-Intent Router — type a customer message (Ctrl-C to quit).")
    try:
        while True:
            msg = input("\nCUSTOMER: ").strip()
            if msg:
                show(msg)
    except (KeyboardInterrupt, EOFError):
        print("\nbye")


if __name__ == "__main__":
    main()
