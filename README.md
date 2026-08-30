# Atlas — a personal life operating system

Atlas is a **secretary that runs your whole life over Telegram.** You talk to it in whatever
language and mess comes out — Egyptian Arabic, English, half of each — and it understands what
you meant, files it under the right part of your life, and every morning at 6:00 (Cairo) hands
you a briefing: today's shape, the three things that matter, what you're neglecting, and one
decision to make. At night it asks what happened and how you felt.

Its one job, above all others: **make sure no part of your life dies silently, and let you stop
carrying it all in your head.**

> Personal project. Not a student-facing Empire product — but it lives in the same ecosystem and
> follows the same operating rules (memory hub is `empire-chronicle`; see `.kiro/steering/`).

---

## What it is (and isn't)

- **Is:** one Telegram bot + a small Python service on the existing Hetzner box, using the tools
  already running there (Groq for understanding, Kokoro TTS for the spoken brief, SQLite for
  memory). Zero new paid dependencies.
- **Isn't:** a to-do app. A to-do app tracks *doing*. Atlas tracks *being* — the standing state
  of each part of your life, and whether it's thriving or quietly flatlining.

## The shape

```
LISTEN → UNDERSTAND → ALLOCATE → BRIEF → ACCOUNT
 talk     Group by      fit finite  6 AM     log what
 freely   intent+domain  hours/energy voice+text happened
```

Five duties of a secretary, delivered through one bot. Release 1 (the "spine") is the smallest
version that already delivers the whole promise; later releases add organs — People, Habits,
Energy, Reviews, Vision — one at a time, behind feature flags.

## Documentation

- **The why** (journey, research, decisions, roadmap): [`docs/`](docs/README.md)
- **The spec:** [`.kiro/specs/atlas-life-os/requirements.md`](.kiro/specs/atlas-life-os/requirements.md)
  · [`design.md`](.kiro/specs/atlas-life-os/design.md) · [`tasks.md`](.kiro/specs/atlas-life-os/tasks.md)
- **Steering / operating rules:** [`.kiro/steering/project-rules.md`](.kiro/steering/project-rules.md)

## Status

Release 1 (the spine) under construction. Deploy is owner-gated — it needs a Telegram bot token
and the server. See `tasks.md` for the live build state.

## Run (once built + configured)

```bash
cp .env.example .env        # fill in TELEGRAM_BOT_TOKEN, OWNER_CHAT_ID, GROQ_API_KEY
docker compose up -d --build
```

Tests (no credentials needed — pure logic is mocked):

```bash
python3.12 -m pip install -r requirements.txt -r requirements-dev.txt
python3.12 -m pytest -q
```
