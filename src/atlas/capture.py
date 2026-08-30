"""Capture orchestration (R1 + R2) — the pure core the Telegram layer calls.

Kept free of any Telegram dependency so it is fully unit-testable: given a db, an
LLM client, and the raw input, it (1) persists the capture BEFORE interpreting
(nothing is ever lost), (2) interprets by meaning, (3) saves a structured item
unless a clarification is needed, (4) archives it, and (5) returns the confirmation
line the owner sees ("understood as …").
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from . import archive
from .database import Database
from .understand import interpret, Understanding, UNASSIGNED, LLMClient


@dataclass
class Ingested:
    capture_id: int
    understanding: Understanding
    item_id: Optional[int]
    confirmation: str


def ingest(db: Database, llm: LLMClient, *, source: str, text: str = "",
           audio_path: str = "", image_path: str = "",
           archive_dir: str = "data/archive",
           now: Optional[datetime] = None,
           names: Optional[list[str]] = None) -> Ingested:
    """Persist → interpret → (maybe) save item → archive → confirm."""
    now = now or datetime.now()

    # 1) persist raw FIRST (R1.5) — a downstream failure can never lose it
    capture_id = db.add_capture(source, raw_text=text, audio_path=audio_path,
                                image_path=image_path, now=now)

    # 2) interpret by meaning, with the live domain list + known names as context
    domains = [(d.name, d.label) for d in db.active_domains()]
    u = interpret(text, domains, llm, names=names)

    # 3a) a SERVICE failure → leave the capture 'unprocessed' so the retry sweep
    #     picks it up automatically when the service returns (R2.7). Nothing lost.
    if u.retryable:
        return Ingested(capture_id, u, None,
                        "📥 Saved — I'll sort this out in a moment.")

    # 3b) genuine ambiguity → ask; do NOT fabricate an item (R2.5)
    if u.needs_clarification:
        db.mark_capture(capture_id, "needs_clarify", understood_json=u.to_json())
        return Ingested(capture_id, u, None, u.confirmation_line())

    item_id = db.save_item(
        capture_id=capture_id, type=u.type, title=u.title, domain=u.domain,
        size=u.size, due=u.due, trigger=u.trigger, confidence=u.confidence, now=now,
    )
    db.mark_capture(capture_id, "processed", understood_json=u.to_json())

    # 4) durable archive (best-effort)
    label = _domain_label(db, u.domain)
    archive.append(archive_dir, u.type, u.title, now,
                   domain=(u.domain if u.domain != UNASSIGNED else None))

    # 5) the confirmation the owner sees, to catch a misread in seconds (R2.6)
    return Ingested(capture_id, u, item_id, u.confirmation_line(domain_label=label))


def retry_unprocessed(db: Database, llm: LLMClient, archive_dir: str = "data/archive",
                      now: Optional[datetime] = None, limit: int = 20) -> int:
    """Re-interpret captures stranded 'unprocessed' when a service was down (R2.7).
    Returns how many were resolved this pass."""
    now = now or datetime.now()
    resolved = 0
    for row in db.unprocessed_captures(limit=limit):
        text = row["raw_text"] or ""
        if not text.strip():
            continue
        domains = [(d.name, d.label) for d in db.active_domains()]
        u = interpret(text, domains, llm)
        if u.needs_clarification:
            continue  # leave it; will be asked / retried later
        db.save_item(capture_id=row["id"], type=u.type, title=u.title, domain=u.domain,
                     size=u.size, due=u.due, trigger=u.trigger, confidence=u.confidence, now=now)
        db.mark_capture(row["id"], "processed", understood_json=u.to_json())
        archive.append(archive_dir, u.type, u.title, now,
                       domain=(u.domain if u.domain != UNASSIGNED else None))
        resolved += 1
    return resolved


def _domain_label(db: Database, name: Optional[str]) -> Optional[str]:
    if not name or name == UNASSIGNED:
        return None
    d = db.get_domain(name)
    return d.label if d else None
