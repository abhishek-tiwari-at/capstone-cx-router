# CX Micro-Intent Router — "The Triage Nurse Before the Bot"

A tiny classifier-agent that sits in front of your CX bot and decides whether a
message needs the **FAQ**, **Empathy**, or **Transaction** agent — or an
**immediate human handoff**. Cheap to build, safe by default: when the router
isn't confident, it escalates instead of guessing.

Built to enterprise standards: guardrails, PII redaction, RAG grounding,
fallbacks, human-in-the-loop for money actions, and structured logging.

## Architecture (six layers per message)

```
Customer message
  [1] INPUT GUARDRAILS   PII redaction · injection/abuse filter · AI disclosure
  [2] MICRO-INTENT ROUTER  intent + confidence + reason  (low conf -> handoff)
  [3] AGENT   FAQ(RAG+cite+abstain) · Empathy · Transaction(human-in-loop) · Handoff
  [4] OUTPUT GUARDRAILS  no fabricated financial promises
  [5] FALLBACKS   every LLM call: retry -> degrade -> human, never crash
  [6] OBSERVABILITY  one JSON trace per message -> data/events.jsonl
```

Handoffs are never a dead end — the **Escalation Briefing Agent** writes a
structured case brief (issue, sentiment, urgency, recommended action) so the
human resolves faster.

## Layout

| Path | What it is |
|---|---|
| `config.py` | Intent taxonomy + thresholds (single source of truth) |
| `src/router.py` | The micro-intent router (the core) |
| `src/rag.py` | Local vector store (swap to a managed DB later) |
| `src/agents/` | faq · empathy · transaction · handoff · escalation_briefing |
| `src/guardrails.py` | PII redaction + input/output checks |
| `src/logging_utils.py` | Structured JSON tracing |
| `src/pipeline.py` | Orchestrates all six layers |
| `eval/` | Build the labeled test set + score the router |
| `scripts/build_kb.py` | Build the RAG index |
| `run.py` | Interactive CLI demo |

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env         # add your ANTHROPIC_API_KEY
python scripts/build_kb.py   # build the RAG index
```

## Use

```bash
python run.py "I was charged twice and I'm furious about it"
python eval/build_testset.py --per-type 12   # then hand-correct data/labeled_testset.csv
python eval/evaluate.py                       # accuracy + confusion matrix + escalation rate
```

## Models (via OpenRouter)

Backend is OpenRouter (OpenAI-compatible API). Router = `anthropic/claude-haiku-4.5`
(fast/cheap), agents = `anthropic/claude-sonnet-4.6`. Set `OPENROUTER_API_KEY` in
`.env`; override model slugs there too. Browse slugs at https://openrouter.ai/models.

## Team TODO (fill in the prompts, own the numbers)

- **Taxonomy + labels** — confirm `config.INTENTS`, hand-label the test set (add
  empathy/handoff cases; ticket type alone can't produce them).
- **Router prompt** — tune `src/router.py` against the labeled set.
- **Baseline** — build a single "one big agent" prompt and compare cost/latency
  to prove the reframe.
  
  
  uvicorn server:app --port 8000
