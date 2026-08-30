# Atlas — Design

Design for **Release 1 (the Spine)**, with seams left for the organs. Traces to `requirements.md`.

---

## 1. Architecture at a glance

Atlas is a single long-running Python process (one Docker container) on the Hetzner box. It is a
Telegram bot with a scheduler and a SQLite brain. It calls two services already on the box (Groq
over the internet; Kokoro on localhost).

```
                    ┌──────────────────────── atlas container ───────────────────────┐
   Telegram  ⇄  bot.py (python-telegram-bot)                                          │
   (owner)       │  handlers: text / voice / photo / forward / commands               │
                 ▼                                                                     │
              capture.py ──persist raw──► database.py (SQLite)  ◄── ledger.py          │
                 │                              ▲                     ▲                │
                 ▼                              │                     │                │
   Groq  ◄── transcribe.py (Whisper)            │                     │                │
   Groq  ◄── understand.py (LLM classify) ──────┘                     │                │
                                                                      │                │
              scheduler.py (APScheduler, Africa/Cairo)                │                │
                 ├─ 06:00 morning brief ─► brief.py ─► voice.py ─► Kokoro (localhost)  │
                 ├─ 21:00 evening close prompt                        │                │
                 └─ hourly guardian sweep ─► guardian.py ─────────────┘                │
                 ▼                                                                     │
              archive.py ──► data/archive/*.md  (durable, portable, git-ignored)       │
                    └────────────────────────────────────────────────────────────────┘
```

**Why a Python service, not a Cloudflare Worker** (the ecosystem uses both): Atlas needs
persistent SQLite state, scheduled background jobs (the 6 AM brief and the guardian sweep that
must run when the owner is absent — R6.5), and localhost access to Kokoro. Workers are stateless
and can't do those. This mirrors `empire-herald` (Telethon + APScheduler + SQLite) — a proven
pattern on this box.

---

## 2. Technology choices

| Concern | Choice | Why |
|---|---|---|
| Bot framework | `python-telegram-bot` 21.x (asyncio) | first-class voice/photo/forward handling; sends voice notes; mature |
| Transcription | **Groq Whisper** (`whisper-large-v3`) | free tier, fast, supports Arabic; on-pattern (ecosystem uses Groq) |
| Understanding | **Groq LLM** (`llama-3.3-70b-versatile`) | free, already primary in the ecosystem; JSON-mode classification |
| Voice out | **Kokoro TTS** on `localhost:8880` | already deployed on the box; OpenAI-compatible `/v1/audio/speech` |
| Storage | **SQLite** (`data/atlas.db`) | zero-setup, perfect for single-user; ecosystem-proven |
| Durable archive | plain **markdown** in `data/archive/` | survives Atlas; portable; passes the 5-year test |
| Scheduling | **APScheduler** (AsyncIOScheduler, `Africa/Cairo`) | in-process cron; same as herald |
| Config | `.env` via `python-dotenv` | secrets never in code |

### The Arabic transcription reality (drives R2.4)
Egyptian-dialect ASR word-error-rate is high (~25–30% for open models on dialect, vs single
digits for read MSA). Atlas therefore treats the transcript as a **noisy signal, not truth**:

1. Keep the original audio always (R1.2) — the ground truth if a transcript misleads.
2. `understand.py` is prompted to correct by **meaning**, given the owner's domain list and known
   names/projects as context — so "يعني الـ lesson بتاعت B2" survives a garbled transcript.
3. The confirmation line (R2.6) echoes the understanding back so a misread is caught in seconds.
4. Low confidence → ask one question (R2.5), never guess silently.

---

## 3. Data model (SQLite schema)

```sql
-- the owner's editable life-areas (R3)
CREATE TABLE IF NOT EXISTS domains (
    name          TEXT PRIMARY KEY,          -- e.g. 'gym'
    label         TEXT NOT NULL,             -- display, e.g. 'Gym / Fitness'
    kind          TEXT NOT NULL DEFAULT 'work',   -- 'work' | 'health' | 'personal'
    neglect_days  INTEGER NOT NULL DEFAULT 7,     -- guardian threshold (R6.3)
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL
);

-- every raw input, persisted BEFORE interpretation (R1.5, R9.5)
CREATE TABLE IF NOT EXISTS captures (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT NOT NULL,
    source        TEXT NOT NULL,             -- 'text'|'voice'|'photo'|'forward'
    raw_text      TEXT,                      -- text, caption, or transcript
    audio_path    TEXT,                      -- retained original voice note (R1.2)
    image_path    TEXT,
    status        TEXT NOT NULL DEFAULT 'unprocessed', -- 'unprocessed'|'processed'|'failed'
    understood_json TEXT                     -- raw LLM interpretation, for audit
);

-- the interpreted, actionable items (R2)
CREATE TABLE IF NOT EXISTS items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    capture_id    INTEGER REFERENCES captures(id),
    created_at    TEXT NOT NULL,
    type          TEXT NOT NULL,             -- 'task'|'idea'|'journal'|'event'
    domain        TEXT REFERENCES domains(name),
    title         TEXT NOT NULL,             -- the cleaned, meaning-corrected phrasing
    size          TEXT,                      -- 'quick'|'medium'|'deep' (tasks)
    due           TEXT,                      -- extracted time signal, nullable
    trigger       TEXT,                      -- implementation-intention ("after morning coffee")
    status        TEXT NOT NULL DEFAULT 'open', -- 'open'|'done'|'dropped'
    confidence    REAL                       -- interpretation confidence 0..1
);

-- what actually happened (R5) — the honest record
CREATE TABLE IF NOT EXISTS ledger (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    at            TEXT NOT NULL,
    domain        TEXT REFERENCES domains(name),
    item_id       INTEGER REFERENCES items(id),
    kind          TEXT NOT NULL,             -- 'completed'|'worked'|'note'
    minutes       INTEGER,                   -- real duration when known (R5.1/R5.3)
    note          TEXT
);

-- daily energy/mood trend (R7.4) — seeds Release 4
CREATE TABLE IF NOT EXISTS feelings (
    day           TEXT PRIMARY KEY,          -- 'YYYY-MM-DD'
    energy        INTEGER,                   -- 1..5
    mood          INTEGER,                   -- 1..5
    note          TEXT,
    created_at    TEXT NOT NULL
);

-- owner-tunable settings + feature flags (spine-first / organs behind flags)
CREATE TABLE IF NOT EXISTS settings (
    key           TEXT PRIMARY KEY,
    value         TEXT NOT NULL
);
```

Every write to `items`, `ledger`, and `feelings` is also appended to a dated markdown file under
`data/archive/` by `archive.py` (R5.4, R9.4).

---

## 4. Module breakdown (`src/atlas/`)

| Module | Responsibility | Key functions |
|---|---|---|
| `config.py` | env + seed domains + timezone; typed `Settings` | `load_settings()`, `SEED_DOMAINS` |
| `database.py` | all SQLite access; schema on boot | `init_db()`, `add_capture()`, `save_item()`, `record_ledger()`, domain CRUD, `attention_since()` |
| `capture.py` | turn a Telegram update into a persisted capture | `handle_text/voice/photo/forward` |
| `transcribe.py` | Groq Whisper wrapper | `transcribe(audio_path) -> str` |
| `understand.py` | Groq LLM classify → structured `Understanding`; meaning-correction; confidence | `interpret(text, domains, names) -> Understanding` |
| `ledger.py` | record completions/durations; per-domain attention aggregation; size-learning | `log_completion()`, `attention_report()`, `learned_size()` |
| `guardian.py` | neglect detection over domains | `neglected(now) -> list[Neglect]` |
| `allocator.py` | order the day: peak-aware, hours-aware, trade-off naming | `plan_day(items, hours, chronotype) -> DayPlan` |
| `brief.py` | compose the morning brief text (shape/top-3/neglect/decision) | `compose_brief(...) -> BriefText` |
| `voice.py` | Kokoro TTS → ogg voice note | `speak(text) -> path` |
| `archive.py` | mirror records to markdown | `append(kind, record)` |
| `scheduler.py` | APScheduler jobs (Africa/Cairo) | `start(app)`: 06:00 brief, 21:00 close, hourly guardian |
| `bot.py` | wire handlers + scheduler; owner-only guard; entrypoint | `main()` |

**Testability seam:** `understand.py`, `transcribe.py`, and `voice.py` take an injected client
(Groq/httpx). Tests pass a fake client, so all pure logic — classification handling, guardian
thresholds, ledger aggregation, allocator ordering, brief composition — runs green with **no
network and no credentials**. (Green tests ≠ correctness, per steering; live verification is a
separate, owner-gated step.)

---

## 5. Key logic

### 5.1 Guardian (R6) — the heart of the product
For each `active` domain: `silent_days = days_since(last ledger/item attention)`. If
`silent_days >= domain.neglect_days`, emit a `Neglect(domain, silent_days, suggested_action)`.
Health domains (gym/diet/deen) seed at 3 days, work at 7 (R6.3), all tunable (stored on the
`domains` row). Runs hourly and, crucially, feeds the 06:00 brief so it fires on absent days (R6.5).

### 5.2 Allocator (R4.3) — morning-peak, hours-bounded, honest
Inputs: today's open items, the confirmed free hours (R4.4), chronotype = morning. Rule set:
place `deep` items in the morning peak; `quick`/admin in the afternoon dip; always protect a
health slot (gym/deen) before day's end. If demand > hours, it does NOT silently drop — it
surfaces the trade-off in words (R4.5) and asks the owner to choose. Deliberately **not** a
clock-time scheduler (out of scope) — it orders and time-boxes, using implementation-intention
triggers ("after morning coffee").

### 5.3 Brief (R4) — a decision, not a list
Ordered sections: **(1) Today's shape** (hours + energy note) · **(2) The 3 that matter** (from
the allocator, deep-work first) · **(3) Neglect** (from guardian) · **(4) One decision**. Written
version + Kokoro voice note of the same. Detailed (2–3 min). Reconciles yesterday's autonomous
filing (R8.1).

### 5.4 Understanding contract
`understand.interpret()` returns a JSON object the rest of the system trusts:
```json
{"type":"task","domain":"empire","title":"record the B2 lesson","size":"deep",
 "due":null,"trigger":"morning peak","confidence":0.82,"clarify":null}
```
`confidence < 0.5` OR `domain == "unassigned"` on an actionable item ⇒ set `clarify` to one short
question and ask (R2.5). The prompt is given the live domain list + known names as context (R2.4).

---

## 6. Scheduled jobs (Africa/Cairo)

| Job | When | Does |
|---|---|---|
| `morning_brief` | 06:00 daily | build + send written brief + voice note (R4) |
| `evening_close` | 21:00 daily | prompt "what happened?" + one feeling question (R7) |
| `guardian_sweep` | hourly | refresh neglect state so the 06:00 brief is current (R6.5) |
| `retry_unprocessed` | every 15 min | re-interpret captures stuck `unprocessed` (R2.7) |

---

## 7. Failure & degradation (R9.6)

- Groq down → capture still saved `unprocessed`; retried; owner still gets a confirmation ("saved,
  I'll sort it shortly").
- Kokoro down → written brief still sent; note "voice unavailable".
- Transcription fails → keep audio; ask owner to type or retry; never drop.
- SQLite is the single source of truth; markdown archive is the backup readable without Atlas.
- Bot only ever answers `OWNER_CHAT_ID`; all else ignored (R1.6, R9.2).

---

## 8. What this design intentionally defers

The schema already carries `feelings` (Release 4) and settings/flags. The organs — People (needs a
`people`/`contacts` table), Habits (`habits`+`habit_log`), full Energy trend, Reviews, Vision — are
additive tables + modules behind flags, and none require reworking the spine. That is the point of
building the spine first.
