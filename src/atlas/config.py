"""Configuration + seed data for Atlas.

Env is read once into a typed Settings object. The seed domains are the owner's
life-areas at first boot; after that the live list lives in the database and is
edited by the owner in plain speech (R3 — domains are DATA, not code).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo


# ── Seed domains (R3.1) ───────────────────────────────────────────────────────
# kind drives the guardian's default neglect threshold: health slides fastest and
# costs the most, so it is watched tightest (R6.3).
#   work    -> 7 days
#   health  -> 3 days
#   personal-> 5 days
SEED_DOMAINS: list[dict] = [
    {"name": "empire",        "label": "Empire / English",        "kind": "work"},
    {"name": "macal",         "label": "MACAL brand & content",   "kind": "work"},
    {"name": "social",        "label": "Social media & marketing","kind": "work"},
    {"name": "trading",       "label": "Trading",                 "kind": "work"},
    {"name": "investing",     "label": "Investing",               "kind": "work"},
    {"name": "learning",      "label": "Learning / courses",      "kind": "work"},
    {"name": "gym",           "label": "Gym / fitness",           "kind": "health"},
    {"name": "diet",          "label": "Diet / nutrition",        "kind": "health"},
    {"name": "deen",          "label": "Deen / worship",          "kind": "health"},
    {"name": "relationships", "label": "Relationships",           "kind": "personal"},
    {"name": "personal",      "label": "Personal",                "kind": "personal"},
]

# Default neglect thresholds by kind, in days (R6.3). Per-domain overrides live on
# the domains row and are owner-tunable.
DEFAULT_NEGLECT_DAYS: dict[str, int] = {"work": 7, "health": 3, "personal": 5}

# Task sizes and a rough default minute-cost, refined per-owner by the ledger (R5.3).
SIZE_MINUTES: dict[str, int] = {"quick": 15, "medium": 45, "deep": 120}


def neglect_days_for(kind: str) -> int:
    """Default neglect threshold for a domain kind."""
    return DEFAULT_NEGLECT_DAYS.get(kind, 7)


@dataclass(frozen=True)
class Settings:
    """Typed runtime configuration, loaded from the environment."""

    telegram_bot_token: str = ""
    owner_chat_id: int = 0

    groq_api_key: str = ""
    # NOTE: this Groq account's catalog has NO llama models — verified live 2026-08-31
    # (available: openai/gpt-oss-120b|20b, qwen/qwen3.8-27b, groq/compound, allam-2-7b).
    # gpt-oss-120b read Egyptian+English code-switch best. Override via GROQ_MODEL.
    groq_model: str = "openai/gpt-oss-120b"
    groq_whisper_model: str = "whisper-large-v3"

    kokoro_url: str = "http://localhost:8880"
    kokoro_voice: str = "af_heart"

    timezone: str = "Africa/Cairo"
    brief_hour: int = 6
    evening_close_hour: int = 21

    db_path: str = "data/atlas.db"
    archive_dir: str = "data/archive"

    # owner chronotype — morning peak (from the owner). Drives the allocator (R4.3).
    chronotype: str = "morning"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def now(self) -> datetime:
        """Timezone-aware 'now' in the owner's zone — the one clock Atlas uses."""
        return datetime.now(self.tz)


def _int(env: str, default: int) -> int:
    raw = os.environ.get(env, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def load_settings(environ: dict | None = None) -> Settings:
    """Build Settings from an environment mapping (defaults to os.environ)."""
    e = os.environ if environ is None else environ

    def get(key: str, default: str = "") -> str:
        return (e.get(key) or default).strip()

    def get_int(key: str, default: int) -> int:
        raw = get(key)
        try:
            return int(raw) if raw else default
        except ValueError:
            return default  # a garbled env value must never crash startup

    return Settings(
        telegram_bot_token=get("TELEGRAM_BOT_TOKEN"),
        owner_chat_id=get_int("OWNER_CHAT_ID", 0),
        groq_api_key=get("GROQ_API_KEY"),
        groq_model=get("GROQ_MODEL", "openai/gpt-oss-120b"),
        groq_whisper_model=get("GROQ_WHISPER_MODEL", "whisper-large-v3"),
        kokoro_url=get("KOKORO_URL", "http://localhost:8880"),
        kokoro_voice=get("KOKORO_VOICE", "af_heart"),
        timezone=get("TIMEZONE", "Africa/Cairo"),
        brief_hour=get_int("BRIEF_HOUR", 6),
        evening_close_hour=get_int("EVENING_CLOSE_HOUR", 21),
        db_path=get("ATLAS_DB_PATH", "data/atlas.db"),
        archive_dir=get("ATLAS_ARCHIVE_DIR", "data/archive"),
        chronotype=get("ATLAS_CHRONOTYPE", "morning"),
    )
