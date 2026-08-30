"""The Guardian — the reason Atlas exists (R6).

It watches every active domain and raises its hand BEFORE a part of the owner's
life goes dark. Health domains (gym/diet/deen) are watched tightest because they
slide fastest and cost the most. Every alarm carries a concrete suggested action —
never bare guilt (R6.4).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .database import Database
from .ledger import attention_report

# A concrete, kind-appropriate nudge for a neglected domain (R6.4).
_SUGGESTIONS = {
    "health": "even 15 minutes today keeps it alive — want me to slot it in?",
    "work": "want me to put one small step on today's plan?",
    "personal": "worth a few minutes today — shall I add it?",
}


@dataclass
class Neglect:
    domain: str
    label: str
    kind: str
    silent_days: int
    threshold: int
    suggested_action: str

    def line(self) -> str:
        """One human line for the brief."""
        return (f"⚠️ {self.label}: {self.silent_days} days quiet "
                f"(limit {self.threshold}) — {self.suggested_action}")


def neglected(db: Database, now: datetime) -> list[Neglect]:
    """Active domains whose silence has met or passed their threshold.

    Sorted worst-first (most overdue relative to its own threshold), so the brief
    leads with the domain most in danger — health outranks work for equal overrun
    because its threshold is smaller.
    """
    report = {a.domain: a for a in attention_report(db, now)}
    out: list[Neglect] = []
    for d in db.active_domains():
        a = report.get(d.name)
        if a is None:
            continue
        if a.silent_days >= d.neglect_days:
            out.append(Neglect(
                domain=d.name,
                label=d.label,
                kind=d.kind,
                silent_days=a.silent_days,
                threshold=d.neglect_days,
                suggested_action=_SUGGESTIONS.get(d.kind, _SUGGESTIONS["work"]),
            ))
    # overrun ratio: how far past its own limit — biggest danger first
    out.sort(key=lambda n: (n.silent_days - n.threshold, -n.threshold), reverse=True)
    return out
