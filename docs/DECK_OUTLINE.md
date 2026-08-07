# Pitch Deck Outline — CX Micro-Intent Router

Per-slide **on-slide bullets** (paste into PowerPoint) + **speaker notes** (what to
say). Grounded in what's actually built — no unmeasured claims. Keep spoken parts
conversational; the slides stay sparse.

**One-line thesis (repeat it twice in the talk):**
*"A cheap triage layer in front of the bot — the model routes and reads tone,
deterministic code decides money, access, and escalation."*

---

## Slide 1 — Title & Team

**On slide:**
- **CX Micro-Intent Router** — *The Triage Nurse Before the Bot*
- A governed front door for LLM customer support
- Team: _<name 1>_ · _<name 2>_ · _<name 3>_
- EXL — GenAI Customer Experience Capstone

**Speaker notes:**
> "We built a triage layer that sits in front of a support bot and decides — before
> any expensive model runs — whether a message should be answered, handled with
> empathy, treated as a transaction, or sent to a human. We call it the CX triage
> nurse: it doesn't try to cure everything, it sorts correctly and knows when not to act."

*Visual: the architecture diagram (`cx_triage_architecture.png`) faded in the background.*

---

## Slide 2 — Problem & Business Context

**On slide:**
- LLM support bots fail two ways: **over-automate** (hallucinate, over-promise,
  unsafe actions) or **under-automate** (everything to humans = slow, costly)
- The real blocker isn't capability — it's **trust**: no safety, no audit trail
- CX teams live on: cost-per-contact, AHT, deflection, CSAT, **compliance incidents**
- Neither approach knows *when it should not act*

**Speaker notes:**
> "Models are good enough today. What keeps enterprises stuck in 'suggest-to-a-human'
> mode is trust — a bot that invents a refund policy or says 'I've refunded you' when
> it hasn't is a brand and compliance risk. The missing piece isn't a smarter answer;
> it's a governed decision about whether the bot should act at all."

---

## Slide 3 — Solution Overview

**On slide:**
- A lightweight **router** classifies every message: **intent + confidence + tone**
  in one cheap call
- Routes to exactly one: **FAQ · Empathy · Transaction · Human handoff**
- **Escalates when unsure**; **fast-tracks angry customers** to a human (churn)
- Safety-critical decisions live in **deterministic, auditable code** — not the model
- The contrarian bet: a **governed front door**, not one self-governing mega-agent

**Speaker notes:**
> "Instead of one big agent doing everything, a tiny classifier decides where each
> message goes. The industry is moving toward a single self-governing agent — we bet
> the opposite. The model reads intent and tone; code decides money, access, and
> escalation. That separation is the whole idea."

---

## Slide 4 — Architecture & Tech Stack

**On slide (the six layers):**
1. **Input guardrails** — PII redaction · injection filter · AI disclosure
2. **Router** — intent + confidence + sentiment (one model call)
3. **Agent** — FAQ (RAG + cite + abstain) · Empathy · Transaction · Handoff
4. **Output guardrails** — block fabricated promises
5. **Fallbacks** — retry → degrade to human, never crash
6. **Observability** — one JSON audit line per message

**Stack:** OpenRouter (Haiku router / Sonnet agents) · Pydantic structured output ·
sentence-transformers RAG · FastAPI dashboard · JSON stores

**Speaker notes:**
> "Every message flows through six layers. The key line: model proposes, code decides.
> The router is cheap Haiku; it only spends the bigger Sonnet agents when the case
> earns it. The $2k limit, ownership check, and idempotency are plain Python — cheaper,
> faster, and impossible to jailbreak around."

*Visual: the six-layer diagram from the README.*

---

## Slide 5 — Solution in Action

**On slide (live dashboard):**
- Chat + **live decision trace** (intent, sentiment, confidence, cost, reason)
- Demo (logged in as **Priya**):
  - `Refund ORD-1001` → **auto-approvable** ($79.99)
  - `Refund ORD-1003` → **human** ($2,499 > $2k — amount from the *order*, not the claim)
  - `Refund ORD-1002` → **blocked: not your order** (access control)
  - furious message → **churn risk → human**
- Mic-drop: *"How do I cancel?"* → FAQ vs *"Cancel now."* → Transaction (**intent ≠ topic**)

**Speaker notes:**
> "Watch the right panel. Same customer, two orders — one auto-approves, one needs a
> human, purely on the real order value. Try to refund someone else's order and it's
> blocked. Send a furious message and it's fast-tracked to a person. The model never
> touches money — it proposes, the code decides."

*Do this LIVE if the connection is stable; otherwise `python demo.py --replay` as backup.*

---

## Slide 6 — Outputs & Evidence

**On slide:**
- **Audit trail** — every decision logged (who, intent, tone, cost, outcome), PII redacted
- **Red-teamed:** IDOR / ownership, amount-spoofing, prompt-injection, social-engineering,
  idempotency — all caught (show `view_logs.py`)
- Grounded FAQ **cites its source**; abstains when unsure (no hallucination)
- ~**$0.004–0.007 / message**; cheap router gates the expensive agents

**Speaker notes:**
> "Everything is logged and defensible — this is what a regulated CX team needs. We
> red-teamed our own agent: you can't refund someone else's order, you can't lowball
> the amount, you can't prompt-inject it into approving money. Here's the audit trail."

*Visual: a `view_logs.py` screenshot showing a blocked ownership attempt + a churn-risk row.*

---

## Slide 7 — Business Value & Scale-Up Path

**On slide — value (directional, to be measured):**
- Cost per contact ↓ · Deflection ↑ · AHT ↓ (briefing) · Compliance incidents ↓ · Churn ↓

**On slide — roadmap:**
1. **Measure** — routing accuracy + cost baseline vs. one-big-agent
2. **Latency** — embedding router for sub-200ms triage
3. **Resilience** — circuit breaker + capacity shedding (Day-9 CCaaS pattern)
4. **Voice** — browser full-duplex through the *same* governed brain
5. **Integrations** — CRM / payments behind existing interfaces

**Speaker notes:**
> "The value is cost, safety, and catching at-risk customers early. Next steps for the
> full hackathon: measure accuracy honestly, make the router sub-200ms with embeddings,
> add load-resilience, and extend to voice — same governed brain, any channel. Nothing
> here is a rewrite; it's the same architecture, hardened."

**Be honest if asked (limitations):** latency (~6–20s today), no conversation memory
(per-message routing), transactions proposed not executed, accuracy not yet measured.

---

## Slide 8 — Thank You

**On slide:**
- **Thank you** — Questions?
- Repo: `github.com/abhishek-tiwari-at/capstone-cx-router`
- One line: *"Not a smarter answer machine — a governed front door you can defend."*

**Speaker notes:**
> "To sum up: the value isn't a better answer, it's knowing when the bot should not
> act — cheaply, safely, and auditably. Happy to take questions."

---

## Anticipated Q&A (keep in your back pocket)

- **"Why not one big agent?"** → *"One agent can answer anything, but it can't decide
  anything about itself — whether it's worth the expensive model, whether it's allowed
  to move money, whether a human should take this. We put those decisions in cheap,
  deterministic, auditable code in front of the model."*
- **"Is this novel?"** → *"The parts aren't — routing, RAG, guardrails all exist. What's
  ours is the discipline: a governed triage front door where the model never holds
  safety-critical authority. That's what makes it deployable."*
- **"Accuracy numbers?"** → *"Not measured yet — the eval harness is built; we'll report
  labeled routing accuracy and a cost baseline for the full hackathon. We won't quote a
  number we haven't earned."*
- **"Latency?"** → *"~6–20s today, two LLM calls. The fix is an embedding router for the
  triage step — sub-200ms — which is on the roadmap."*
