# 04 · Roadmap

Six releases. The **spine** ships first and already delivers the north star on its own; the
**organs** are added one at a time, each behind a feature flag, only after the spine is trusted in
real use. Full task detail: [`../.kiro/specs/atlas-life-os/tasks.md`](../.kiro/specs/atlas-life-os/tasks.md).

---

## Release 1 — the Spine ✅ *code complete, deploy pending*
Capture · Understand · Allocate (basic, peak-aware) · Morning Brief (text + voice) · Ledger ·
Guardian · Evening close + one feeling question.

**Delivers the entire success metric on its own:** the owner can offload anything by voice/text and
trust it's filed; gets a decided 06:00 brief; and is warned before gym/diet/deen (3d) or a venture
(7d) goes dark. 57 unit tests green; runtime wiring verified against the real libraries.

**Remaining for Release 1:** deploy (owner-gated — BotFather token + server), then live use with
real voice notes for a few days.

## Release 2 — People 🔜 *(organ #1)*
Relationships in Dunbar tiers (~5/15/50), last-contact tracking, gentle "reach out to X" nudges.
The domain that most predicts a good life and dies silently too. Chosen first because it's
high-value and rarely built.

## Release 3 — Habits & Routines
gym / diet / deen / reading / sleep as anchored, tracked habits (shrink → anchor → celebrate).
Feeds the Guardian with streak/state data.

## Release 4 — Energy & Mood (full)
The daily check-in grows into a trend line; the allocator becomes truly energy-aware and eases the
load when the trend drifts down over a week.

## Release 5 — Reviews
Weekly first — short, opt-in, celebratory-first (the owner is new to reviews) — then monthly and
quarterly once the weekly habit sticks.

## Release 6 — Vision & Values
Values + long-horizon goals that every day is checked against; the annual review anchors the
vertical thread so days ladder up to a life.

---

## Priority order (owner delegated the call)
Guardian (in the spine) → **People → light daily check-in → Habits → full Energy → Reviews →
Vision.**

## Deploy checklist (owner-gated — Release 1 → live)
1. Create a bot with **@BotFather** → copy the token.
2. Get the owner's numeric chat id (**@userinfobot**).
3. On the box: set `TELEGRAM_BOT_TOKEN`, `OWNER_CHAT_ID`, `GROQ_API_KEY` in `.env`.
4. `docker compose up -d --build`; send a voice note → expect "✅ Got it — …" in seconds.
5. Verify the 06:00 brief (text + voice) against the live box + Kokoro.
6. Add Atlas to the box's watchdog + nightly backup; record it in `empire-chronicle`.
