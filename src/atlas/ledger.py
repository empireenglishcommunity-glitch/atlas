"""Account for what actually happened (R5) — the honest record that keeps briefs real.

Two jobs:
  1. Record completions/work with real durations.
  2. Report, per domain, how much attention it got — and learn the owner's true task
     durations so the allocator stops believing the planning fallacy (R5.3).
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from . import config as cfg
from .database import Database


@dataclass
class DomainAttention:
    domain: str
    label: str
    kind: str
    minutes: int              # minutes logged in the window
    items_touched: int        # ledger entries in the window
    last_attention: Optional[datetime]
    silent_days: int          # whole days since last attention (0 if today)


def log_completion(db: Database, item_id: int, minutes: Optional[int] = None,
                   note: str = "", now: Optional[datetime] = None) -> None:
    """Mark an item done and record it (with real duration when known)."""
    item = db.get_item(item_id)
    domain = item.domain if item else None
    db.set_item_status(item_id, "done")
    db.record_ledger(domain, "completed", item_id=item_id, minutes=minutes,
                     note=note, now=now)


def log_work(db: Database, domain: str, minutes: int, note: str = "",
             now: Optional[datetime] = None) -> None:
    """Record time spent on a domain that isn't tied to a specific item."""
    db.record_ledger(domain, "worked", minutes=minutes, note=note, now=now)


def _silent_days(reference: Optional[datetime], now: datetime) -> int:
    if reference is None:
        return 10**6  # effectively "forever" — caller decides using a baseline
    delta = now - reference
    return max(0, delta.days)


def attention_report(db: Database, now: datetime, window_days: int = 7
                     ) -> list[DomainAttention]:
    """Per active domain, attention over the trailing window + silence length.

    'Silent days' is measured from the last attention OR the domain's creation
    (whichever is later), so a freshly added domain is not instantly 'neglected'.
    """
    since = now - timedelta(days=window_days)
    out: list[DomainAttention] = []
    for d in db.active_domains():
        last = db.last_attention(d.name)
        baseline = last
        if baseline is None and d.created_at:
            try:
                baseline = datetime.fromisoformat(d.created_at)
            except ValueError:
                baseline = None
        out.append(DomainAttention(
            domain=d.name,
            label=d.label,
            kind=d.kind,
            minutes=db.domain_minutes_since(d.name, since),
            items_touched=_count_since(db, d.name, since),
            last_attention=last,
            silent_days=_silent_days(baseline, now),
        ))
    return out


def _count_since(db: Database, domain: str, since: datetime) -> int:
    with db._conn() as c:
        r = c.execute(
            "SELECT COUNT(*) AS n FROM ledger WHERE domain=? AND at>=?",
            (domain, since.isoformat()),
        ).fetchone()
    return int(r["n"] or 0)


def learned_size_minutes(db: Database, domain: str, size: str) -> int:
    """Best estimate of how long a task of this domain+size REALLY takes.

    Uses the median of the owner's own history when there's enough of it;
    otherwise the generic default. This is how Atlas stops calling a task 'quick'
    when the owner's 'quick' has historically run long (R5.3).
    """
    history = db.item_durations(domain, size)
    if len(history) >= 3:
        return int(statistics.median(history))
    return cfg.SIZE_MINUTES.get(size, 45)
