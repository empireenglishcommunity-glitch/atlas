# 03 · Locked Decisions

Decisions made with the owner during design. **Do not silently reverse these** — each has reasoning
behind it. If one needs to change, change it deliberately and note why.

---

## Product identity
- **Name: Atlas.** English, chosen by the owner — deliberately outside the ecosystem's Arabic-concept
  naming (Ijtihad, Itqan, Darb…) because this is a *personal* system, not a student-facing product.
- **It is a life OS, not a productivity app.** It tracks the *state* of each life domain, not just a
  task list.
- **North star:** *no part of life dies silently, and the owner stops carrying it in his head.*

## The owner's answers that shaped it
- **Capture:** all channels (text, voice, photo, forward) — the owner switches by moment; they
  converge to one inbox.
- **Daily brief:** 06:00 Africa/Cairo, **detailed** (2–3 min), as a **written message + spoken
  voice note**.
- **Chronotype:** morning-active → deep work is placed in the morning peak.
- **Autonomy:** a **strict secretary with spine** — it files confidently, pushes back, but always
  reconciles what it did in the brief and leaves decisions to the owner.
- **Nudging:** heavy, but every nudge carries an action — never bare guilt.
- **Emotional check-in:** yes, important — one light question at the evening close, from day one.
- **Reviews:** the owner doesn't do them yet → Atlas introduces them gently, weekly-first,
  celebratory before corrective.
- **Domains:** editable by the owner in plain speech; real estate removed; **gym / diet / deen** are
  first-class and watched tightest.

## Architecture
- **Runs on the existing $7/month Hetzner box** as one Docker container. Zero new paid
  dependencies.
- **Python service, not a Cloudflare Worker** — it needs persistent SQLite state, scheduled
  background jobs (the guardian must run on absent days), and localhost access to Kokoro. Mirrors
  the proven `empire-herald` pattern.
- **Groq** for both Whisper transcription and LLM understanding (free tier, already the ecosystem's
  primary). **Kokoro TTS** on localhost:8880 for the spoken brief (already on the box). **SQLite**
  for the operating store; **plain-markdown archive** for durability.
- **Single-user, maximum privacy:** Atlas talks only to the owner's chat id; its data store holds a
  whole life and is treated as maximally sensitive; `data/` is git-ignored and never committed.

## Product principles (hard rules)
- **Advise, never command** — autonomy is a psychological need; a bossy tool gets muted.
- **Spine first, organs behind flags** — deploy dormant, release deliberately.
- **The surface stays tiny** — only the morning brief, the evening close, and (later) the weekly
  review are ever shown; breadth lives under the hood.
- **Never lose a capture** — persist the raw input before interpreting it; on a service failure keep
  it and retry, never drop.
- **Treat transcription as noisy** — correct by meaning, keep the audio, ask when unsure rather than
  guess.
- **A green test suite is not proof of correctness** — verify against the running thing before
  claiming "done."

## Neglect thresholds (owner-tunable)
- Work domains: ~7 days of silence → alarm.
- Health domains (gym / diet / deen): ~3 days → alarm (they slide fastest and cost the most).
- New domains don't alarm until their threshold has elapsed since creation.

## Deliberately out of scope
Multi-user/sharing · a web or mobile UI (Telegram is the whole surface) · auto-scheduling exact
clock times (brittle — Atlas proposes allocations + triggers, it doesn't seize the calendar) · any
paid or usage-capped service.
