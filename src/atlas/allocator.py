"""The Allocator — fit the day against FINITE time, morning-peak first (R4.3-4.5).

Time is the owner's #1 resource, and his days vary wildly, so the allocator never
pretends there's room that isn't there. It:
  1. prioritises open tasks (due/overdue → deep leverage → oldest),
  2. time-boxes them against the confirmed free hours using LEARNED durations,
  3. places deep work in the morning peak, lighter work later,
  4. and when demand exceeds the budget it does NOT silently drop — it names the
     trade-off so the owner decides (R4.5).
It deliberately does not assign clock times (brittle, out of scope) — it orders,
sizes, and attaches an implementation-intention slot.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from . import config as cfg
from .database import Item

# morning chronotype → where each size belongs in the day
_MORNING_SLOTS = {"deep": "morning peak", "medium": "midday", "quick": "afternoon"}
_SIZE_RANK = {"deep": 0, "medium": 1, "quick": 2}


@dataclass
class Slotted:
    item: Item
    minutes: int
    slot: str


@dataclass
class DayPlan:
    scheduled: list[Slotted] = field(default_factory=list)
    deferred: list[Item] = field(default_factory=list)
    budget_minutes: int = 0
    planned_minutes: int = 0
    over_capacity: bool = False
    tradeoff: Optional[str] = None

    @property
    def top(self) -> list[Slotted]:
        """The 3 that matter — deep-work-first, for the brief."""
        return self.scheduled[:3]


def _is_due_soon(item: Item, today: str) -> bool:
    if not item.due:
        return False
    d = item.due.strip().lower()
    return today in d or "today" in d or "النهارده" in d or "delam" in d or "overdue" in d


def _priority(item: Item, today: str) -> tuple:
    """Lower sorts first: due-soon, then deep leverage, then older (by id/created)."""
    due_rank = 0 if _is_due_soon(item, today) else 1
    size_rank = _SIZE_RANK.get(item.size or "medium", 1)
    return (due_rank, size_rank, item.created_at or "", item.id)


def plan_day(items: list[Item], free_hours: float, now: datetime,
             chronotype: str = "morning",
             size_minutes: Optional[Callable[[Item], int]] = None) -> DayPlan:
    """Build the day plan. `size_minutes` lets the caller inject LEARNED durations
    (from the ledger); default falls back to the generic size table."""
    budget = int(round(free_hours * 60))
    today = now.date().isoformat()

    def est(it: Item) -> int:
        if size_minutes:
            return max(5, size_minutes(it))
        return cfg.SIZE_MINUTES.get(it.size or "medium", 45)

    tasks = [it for it in items if it.type in ("task", "event")]
    tasks.sort(key=lambda it: _priority(it, today))

    plan = DayPlan(budget_minutes=budget)
    spent = 0
    for it in tasks:
        m = est(it)
        if spent + m <= budget or not plan.scheduled:
            # always place at least one item, even on a tiny day, so there's a start
            slot = _MORNING_SLOTS.get(it.size or "medium", "midday") \
                if chronotype == "morning" else "when you can"
            plan.scheduled.append(Slotted(item=it, minutes=m, slot=slot))
            spent += m
        else:
            plan.deferred.append(it)

    plan.planned_minutes = spent
    plan.over_capacity = bool(plan.deferred) or spent > budget

    if plan.over_capacity and plan.deferred:
        top_defer = plan.deferred[0]
        plan.tradeoff = (
            f"You have ~{_fmt_hours(budget)} today but {_fmt_hours(spent + _rough(plan.deferred, est))} "
            f"of work wants in. I front-loaded the {len(plan.scheduled)} that matter; "
            f"“{top_defer.title}” and {max(0, len(plan.deferred) - 1)} more wait unless you "
            f"make room. Your call."
        )
    return plan


def _rough(items: list[Item], est: Callable[[Item], int]) -> int:
    return sum(est(it) for it in items)


def _fmt_hours(minutes: int) -> str:
    h = minutes / 60
    if h < 1:
        return f"{minutes}m"
    if h == int(h):
        return f"{int(h)}h"
    return f"{h:.1f}h"
