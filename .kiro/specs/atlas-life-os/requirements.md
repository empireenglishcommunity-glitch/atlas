# Atlas — Requirements

**Status:** Release 1 (the Spine) is the active scope. Releases 2–6 (organs) are captured here as
future requirements so the design doesn't paint itself into a corner, but they are NOT built yet.

**Notation:** acceptance criteria use EARS ("WHEN <trigger> THE SYSTEM SHALL <response>" /
"WHERE <state> …" / "IF <condition> THEN …"). "The owner" = the single user, Mahmoud.

---

## Vision & guiding principle

Atlas is a personal secretary that runs the owner's whole life through Telegram. The owner
speaks freely; Atlas understands, files, allocates against finite time and energy, briefs him
each morning, and accounts for what happened. Its overriding purpose:

> **No part of the owner's life dies silently, and the owner stops carrying his life in his head.**

Every requirement serves that sentence. A requirement that doesn't is out of scope.

---

# RELEASE 1 — THE SPINE (active scope)

## R1 — Frictionless capture

**User story:** As the owner, I want to throw a thought at Atlas in under 5 seconds by any means,
so that capturing never competes with the idea itself.

1. WHEN the owner sends a **text** message THE SYSTEM SHALL accept it as a capture without any
   required form, tag, or category.
2. WHEN the owner sends a **voice note** THE SYSTEM SHALL accept it, transcribe it, and retain the
   original audio file.
3. WHEN the owner sends a **photo** (with or without caption) THE SYSTEM SHALL accept it and store
   the image plus any caption as a capture.
4. WHEN the owner **forwards** a message from elsewhere THE SYSTEM SHALL accept its content as a
   capture.
5. WHEN any capture is received THE SYSTEM SHALL persist it durably BEFORE attempting to interpret
   it, so interpretation failure can never lose the input.
6. WHERE the sender's chat id is not the configured `OWNER_CHAT_ID` THE SYSTEM SHALL ignore the
   message entirely (single-user privacy).
7. WHEN a capture is persisted THE SYSTEM SHALL reply within a few seconds with an explicit
   confirmation, so the owner never wonders whether it was lost.

## R2 — Understanding (interpret the mess)

**User story:** As the owner, I want Atlas to figure out what I meant from broken, code-switched
speech, so I don't have to phrase things carefully or classify them myself.

1. WHEN a capture is interpreted THE SYSTEM SHALL determine its **type** — one of: task, idea,
   journal/note, event, or (later releases) person / expense / feeling.
2. WHEN a capture is interpreted THE SYSTEM SHALL assign it to exactly one **domain** from the
   owner's current editable domain list, or mark it `unassigned` if none fits.
3. WHEN a capture is a task THE SYSTEM SHALL estimate a rough **size** (quick / medium / deep) and
   extract any time/urgency signal present.
4. WHERE the input is Egyptian Arabic, English, or a mix THE SYSTEM SHALL interpret by **meaning**,
   using the owner's known domains and names as context, and SHALL NOT assume the transcription is
   literally correct.
5. WHEN interpretation confidence is low THE SYSTEM SHALL ask the owner one short clarifying
   question rather than guessing silently.
6. WHEN interpretation succeeds THE SYSTEM SHALL include a one-line "understood as: …" in its
   confirmation so the owner can catch a misread immediately.
7. IF the LLM or transcription service is unavailable THEN THE SYSTEM SHALL still persist the raw
   capture as `unprocessed` and retry interpretation later, never dropping it.

## R3 — Editable domains

**User story:** As the owner, I want to add or retire life-areas by just telling Atlas, so the
system bends to my life instead of me bending to it.

1. THE SYSTEM SHALL store the domain list as data (not code), seeded with: Empire/English, MACAL
   brand & content, social & marketing, trading, investing, learning/courses, gym, diet, deen,
   personal, relationships.
2. WHEN the owner says (in any phrasing) to add a domain THE SYSTEM SHALL add it and confirm.
3. WHEN the owner says to retire/rename a domain THE SYSTEM SHALL do so without losing historical
   records already filed under it.
4. WHERE a domain is retired THE SYSTEM SHALL stop allocating and stop raising neglect alarms for it.

## R4 — The morning brief

**User story:** As the owner, at 6 AM I want a briefing I can read or listen to that tells me the
shape of my day already decided, so I act in one glance instead of facing a raw list.

1. WHEN the local time reaches `BRIEF_HOUR` in `Africa/Cairo` THE SYSTEM SHALL send the owner a
   **written brief** and a **spoken voice note** of the same brief.
2. THE brief SHALL contain, in order: today's shape, the **top 3** priorities, an explicit
   **neglect callout** (what's going quiet), and **one decision** to make.
3. WHERE the owner is a morning-peak chronotype THE SYSTEM SHALL place deep-work items earlier in
   the day and lighter/admin items into the afternoon.
4. WHEN building the brief THE SYSTEM SHALL first confirm the day's available focus hours (the
   owner's days vary widely) via a quick prompt or a remembered default.
5. WHEN presenting trade-offs THE SYSTEM SHALL name them explicitly (e.g. "2h to trading means
   deen gets 0 today") rather than hiding the cost.
6. THE brief SHALL be detailed (a 2–3 minute listen), not a one-line glance.
7. IF Kokoro TTS is unavailable THEN THE SYSTEM SHALL still send the written brief and note that
   audio was unavailable.

## R5 — The ledger (account for what happened)

**User story:** As the owner, I want Atlas to know what actually got done and how long it really
took, so its future briefs are honest and not fantasy.

1. WHEN an item is completed THE SYSTEM SHALL record the completion, its domain, and (where known)
   its real duration.
2. THE SYSTEM SHALL aggregate, per domain, how much attention (items + time) each domain received
   over recent days.
3. WHEN estimating a task's size THE SYSTEM SHALL learn from the owner's own history (fighting the
   planning fallacy: if "quick" tasks in a domain historically ran long, stop calling them quick).
4. THE SYSTEM SHALL retain the ledger durably and mirror it to a plain-markdown archive.

## R6 — The guardian (neglect detector) — *the reason Atlas exists*

**User story:** As the owner, I want to be told before a part of my life goes dark, so nothing
ever dies silently.

1. THE SYSTEM SHALL track, per active domain, the time since it last received meaningful attention.
2. WHERE a domain's silence exceeds its threshold THE SYSTEM SHALL raise it in the morning brief.
3. THE default thresholds SHALL be ~7 days for work domains and ~3 days for gym, diet, and deen;
   each SHALL be tunable by the owner in plain speech.
4. WHEN raising a neglect alarm THE SYSTEM SHALL pair it with a concrete suggested action, never
   bare guilt.
5. THE guardian SHALL run even on days the owner never opens or messages Atlas.

## R7 — The evening close + feeling check-in

**User story:** As the owner, at night I want a 20-second wrap that also asks how I'm doing, so
the day is closed and my state is tracked.

1. WHEN the local time reaches `EVENING_CLOSE_HOUR` THE SYSTEM SHALL prompt the owner with a short
   "what happened today?" and record the reply into the ledger.
2. THE evening close SHALL include exactly **one** light question about energy/mood, and SHALL
   accept a one-tap or one-word answer.
3. WHERE the owner does not respond THE SYSTEM SHALL NOT nag repeatedly that night; it records "no
   close" and moves on.
4. THE SYSTEM SHALL store the feeling/energy reading as a trend series for later releases.

## R8 — Strict-but-respectful autonomy & nudging

**User story:** As the owner, I want a secretary with spine that pushes back and reminds me a lot,
but never bosses me, so I trust it and don't mute it.

1. THE SYSTEM SHALL classify and file confidently without asking, BUT SHALL reconcile every
   autonomous action in the next brief ("here's what I did with your words").
2. WHEN the owner is overloaded in one domain THE SYSTEM SHALL push back (gatekeep) rather than
   silently pile on.
3. WHEN Atlas nudges THE SYSTEM SHALL always attach an action; a nudge SHALL never be pure guilt.
4. WHERE the owner ignores a nudge for 2–3 days THE SYSTEM MAY escalate tone, but SHALL always
   leave the decision with the owner.
5. THE SYSTEM SHALL present recommendations, never commands (supports autonomy — a psychological
   need).

## R9 — Cost, privacy, durability (non-functional)

1. THE SYSTEM SHALL run within the existing $7/month box with no new paid dependency.
2. THE SYSTEM SHALL respond only to `OWNER_CHAT_ID` and SHALL keep all life data on the owner's own
   infrastructure.
3. THE SYSTEM SHALL never commit runtime data or secrets to git.
4. THE SYSTEM SHALL keep a plain-markdown archive so the owner's life log survives Atlas itself.
5. THE SYSTEM SHALL persist raw input before interpretation so no capture is ever lost to a
   downstream failure.
6. WHERE a background service (Groq, Kokoro) is down THE SYSTEM SHALL degrade gracefully, never crash.

---

# FUTURE RELEASES (captured, not yet built)

## R10 — People organ (Release 2)
Track relationships in Dunbar tiers (~5 / 15 / 50); record last-contact; nudge the owner to reach
out to inner-circle contacts gone quiet. Relationships are a domain that dies silently too.

## R11 — Habits & routines (Release 3)
Model gym / diet / deen / reading / sleep as anchored, tracked habits (shrink, anchor to an
existing routine, celebrate). Feed the guardian with streak/state data.

## R12 — Energy & mood, full (Release 4)
Grow the daily check-in into a trend line; make the allocator truly energy-aware; ease the load
when the trend drifts down over a week.

## R13 — Reviews (Release 5)
Introduce a short weekly review (opt-in, celebratory-first because the owner is new to reviews),
then monthly/quarterly once the weekly habit sticks.

## R14 — Vision & values (Release 6)
Hold values + long-horizon goals; check daily allocation against them; anchor with an annual
review. Make days ladder up to a life (self-concordant goals reduce conflict).

---

## Out of scope (deliberately)

- Multi-user / sharing. Atlas is single-user by design.
- A web or mobile UI. Telegram is the entire surface.
- Auto-scheduling exact clock times without owner input (brittle, high-maintenance) — Atlas
  proposes allocations and implementation-intention triggers, it does not seize the calendar.
- Any paid API or usage-capped service.
