# Atlas — AI Agent Steering Rules

> Auto-loaded by Kiro. Read this at the start of every session working on Atlas.

## Session protocol

The canonical, ecosystem-wide protocol (`/start`, `/sync`, `/checkpoint` + standing rules) lives
in `empireenglishcommunity-glitch/empire-chronicle/.kiro/steering/AI-AGENT-PROTOCOL.md`. Read it
first. `empire-chronicle` is the memory hub for the whole org, Atlas included.

## Project identity

- **Project:** Atlas — the owner's personal life operating system (a Telegram secretary).
- **Owner:** Mahmoud Ashri (@macal_emperor).
- **Not** a student-facing Empire product. It is personal, single-user. This is why its name is
  English (owner's explicit choice) rather than the ecosystem's Arabic-concept convention.
- **Runs on:** the existing Hetzner box (`77.42.43.250`) as a Docker container, alongside the
  Empire services. Zero new paid dependencies.

## Architecture principles (MUST follow — inherited from the ecosystem)

- **Zero / near-zero cost.** Groq free tier, self-hosted Kokoro, SQLite. No usage-capped SaaS.
- **No vendor lock-in.** Local SQLite + plain-markdown archive. If Atlas dies, the owner's life
  log is still readable and portable.
- **Single user, maximum privacy.** Atlas talks ONLY to `OWNER_CHAT_ID`. It holds a person's
  whole life — treat its data store as maximally sensitive. `data/` is git-ignored; never commit it.
- **Advise, never command.** Atlas is a secretary with spine: it proposes, names trade-offs, and
  pushes back — but the owner decides. This is a hard product rule (autonomy is a psychological
  need; a tyrant tool gets abandoned).
- **Spine first, organs behind flags.** Deploy dormant, release deliberately. A new capability is
  wrapped in a feature flag, defaulting OFF, exactly like the Empire bot.
- **The surface stays tiny.** Breadth lives under the hood; the only things the owner touches are
  the morning brief, the evening close, and (later) the weekly review.

## Hard rules

- **Never push to `main`.** Branch + PR, even docs-only. Create PRs with
  `gh api repos/{owner}/{repo}/pulls -f ...` (the `gh pr` subcommands fail in this sandbox).
- **Never commit a secret.** Tokens/keys live only in `.env` (git-ignored) or the server env.
  A committed secret is a live incident requiring rotation.
- **A green test suite is NOT proof of correctness.** Verify against the running thing.
- **Arabic-first understanding.** The owner speaks Egyptian Arabic mixed with English. The
  understanding layer must handle broken, code-switched input and correct by *meaning* — never
  assume clean transcription (Egyptian-dialect ASR word-error-rate is high; keep the original audio).
- **Deploy is owner-gated.** Building/testing happens here; deployment needs the Telegram token
  and server access, which do not survive between sessions.
