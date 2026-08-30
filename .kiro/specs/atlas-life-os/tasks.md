# Atlas — Implementation Plan

> **Status header (trust this, not the checkboxes below — ecosystem rule):**
> **Release 1 (Spine) — CODE COMPLETE, 57 tests green, deploy pending (owner-gated).**
> Phases 0–5 built and unit-tested; the Telegram + scheduler wiring imports cleanly against
> the real libraries. Phase 6 (live deploy) needs a BotFather token + the server, which are
> not available in the build sandbox. Releases 2–6 (organs) are planned, not started.

Each task cites the requirements it satisfies. Build order is spine-first; organs are added only
after the spine is trusted in real use.

---

## RELEASE 1 — THE SPINE

### Phase 0 — Scaffold  ✅
- [x] 0.1 Project structure, README, `.kiro/steering`, `.gitignore` (ignores `data/` + secrets)
- [x] 0.2 `requirements.txt`, `requirements-dev.txt`, `.env.example`, `Dockerfile`, `docker-compose.yml`
- [x] 0.3 Spec: `requirements.md`, `design.md`, `tasks.md`

### Phase 1 — Foundation (data + config)
- [x] 1.1 `config.py`: typed settings from env, `SEED_DOMAINS`, timezone helpers _(R3.1, R9)_
- [x] 1.2 `database.py`: schema (`domains`, `captures`, `items`, `ledger`, `feelings`, `settings`),
      `init_db()`, seed domains on first boot _(R1.5, R3.1, R9.5)_
- [x] 1.3 `database.py` CRUD: captures, items, domains (add/retire/rename), settings _(R3.2–3.4)_
- [x] 1.4 `archive.py`: mirror items/ledger/feelings to dated markdown _(R5.4, R9.4)_
- [x] 1.5 Tests: schema init, capture persistence-before-processing, domain add/retire keeps history

### Phase 2 — Understanding
- [x] 2.1 `transcribe.py`: Groq Whisper wrapper, injectable client _(R1.2, R2.4)_
- [x] 2.2 `understand.py`: LLM classify → `Understanding` (type/domain/size/due/trigger/confidence/
      clarify); prompt carries live domains + names; JSON output _(R2.1–2.6)_
- [x] 2.3 Low-confidence / unassigned → one clarifying question path _(R2.5)_
- [x] 2.4 Retry path for `unprocessed` captures when services return _(R2.7)_
- [x] 2.5 Tests (fake LLM client): task/idea/journal routing, domain assignment, low-confidence →
      clarify, code-switched-meaning correction, service-down → stays `unprocessed`

### Phase 3 — Account + Guardian
- [x] 3.1 `ledger.py`: `log_completion()`, `attention_report()` per domain, `learned_size()` _(R5)_
- [x] 3.2 `guardian.py`: per-domain neglect with tunable thresholds + suggested action _(R6)_
- [x] 3.3 Tests: attention aggregation, planning-fallacy size-learning, neglect at 3d/7d boundaries,
      retired domain raises no alarm

### Phase 4 — Allocate + Brief + Voice
- [x] 4.1 `allocator.py`: peak-aware, hours-bounded ordering; trade-off surfacing _(R4.3–4.5)_
- [x] 4.2 `brief.py`: compose shape / top-3 / neglect / one-decision; reconcile autonomous filing _(R4, R8.1)_
- [x] 4.3 `voice.py`: Kokoro `/v1/audio/speech` → ogg; graceful fallback _(R4.7)_
- [x] 4.4 Tests: allocator ordering (deep→AM), over-capacity → trade-off named, brief section order,
      brief builds text-only when Kokoro is down

### Phase 5 — Wiring (Telegram + scheduler)
- [x] 5.1 `capture.py`: text / voice / photo / forward handlers → persist → interpret → confirm
      with "understood as" line _(R1.1–1.7, R2.6)_
- [x] 5.2 Owner-only guard on every handler _(R1.6, R9.2)_
- [x] 5.3 Command surface: `/domains`, add/retire domain by speech, `/today`, mark done, tune
      thresholds _(R3.2–3.4, R6.3)_
- [x] 5.4 `scheduler.py`: 06:00 brief, 21:00 evening close + feeling question, hourly guardian,
      15-min retry _(R4.1, R6.5, R7)_
- [x] 5.5 `bot.py`: assemble handlers + scheduler + owner guard; entrypoint _(all)_
- [x] 5.6 Full `pytest` green; manual dry-run notes for owner-gated live steps

### Phase 6 — Deploy (OWNER-GATED — not in build sandbox)
- [ ] 6.1 Owner creates a BotFather token; sets `.env` on the box
- [ ] 6.2 `docker compose up -d --build`; verify capture → confirm round-trip
- [ ] 6.3 Verify 06:00 brief (text + voice) against the live box + Kokoro
- [ ] 6.4 Owner uses it with real voice notes for a few days before any organ is added
- [ ] 6.5 Add Atlas to the box's watchdog + nightly backup; record in `empire-chronicle`

---

## RELEASE 2 — PEOPLE  _(organ #1, flag-gated)_ — planned
- [ ] `contacts` table (name, tier 5/15/50, last_contact, cadence); reach-out nudges in the brief;
      capture "talked to X" → updates last_contact _(R10)_

## RELEASE 3 — HABITS & ROUTINES  _(flag-gated)_ — planned
- [ ] `habits` + `habit_log`; anchor/shrink/celebrate model; feed guardian with streak state _(R11)_

## RELEASE 4 — ENERGY & MOOD (full)  _(flag-gated)_ — planned
- [ ] Trend analytics over `feelings`; energy-aware allocator; auto-ease load on a downward week _(R12)_

## RELEASE 5 — REVIEWS  _(flag-gated)_ — planned
- [ ] Weekly review (opt-in, celebratory-first); then monthly/quarterly _(R13)_

## RELEASE 6 — VISION & VALUES  _(flag-gated)_ — planned
- [ ] Values + long-horizon goals; daily allocation checked against them; annual review _(R14)_

---

## Definition of done — Release 1
The owner can fire any input to one Telegram bot and get an instant "got it — understood as …,
filed under [domain]"; at 06:00 Cairo receive a detailed written + spoken brief (shape / top-3 /
neglect / one decision); get a 20-second evening close with one feeling question; and be warned
before gym/diet/deen (3d) or a venture (7d) goes dark — all on the $7 box, in plain-text-backed
storage. That alone satisfies the north star: *nothing dies silently, and he stops carrying it in
his head.*
