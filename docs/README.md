# Atlas — Project Documentation

This folder is the **why** behind Atlas. The code and the formal spec live elsewhere; this is the
record of how we got here — the problem, the research, the decisions, and the plan — so the
thinking is never lost and any future session (human or AI) can pick up with full context.

| Doc | What's in it |
|---|---|
| [`01-the-journey-and-vision.md`](./01-the-journey-and-vision.md) | How Atlas went from "a place to dump tasks" to a whole-life secretary; the two-axis vision and the "organs" |
| [`02-research-foundations.md`](./02-research-foundations.md) | The science every design choice rests on, with sources |
| [`03-decisions.md`](./03-decisions.md) | Every locked decision and the reasoning — do not silently reverse these |
| [`04-roadmap.md`](./04-roadmap.md) | The six releases, what's built, what's next |

**The formal engineering spec** (requirements / design / phased tasks) lives in
[`../.kiro/specs/atlas-life-os/`](../.kiro/specs/atlas-life-os/).

---

## One-paragraph summary

Atlas is a **personal secretary that runs a whole life over Telegram**. The owner speaks freely —
Egyptian Arabic, English, or a mix — and Atlas understands the meaning, files it under the right
part of life, allocates it against finite time and energy, and at 06:00 Cairo delivers a briefing
(written + spoken) of the day's shape, the three things that matter, what's being neglected, and
one decision to make. At night it asks what happened and how the owner felt. Its overriding
purpose: **no part of life dies silently, and the owner stops carrying it all in his head.**

## Status (2026-08-30)

- **Release 1 — the Spine:** code complete, 57 unit tests green, runtime wiring verified against
  the real libraries. Deploy is owner-gated (needs a Telegram token + the server).
- **Releases 2–6 — the organs** (People, Habits, Energy, Reviews, Vision): planned, not started.
