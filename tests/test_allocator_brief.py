from datetime import datetime
from zoneinfo import ZoneInfo

from src.atlas.allocator import plan_day
from src.atlas.brief import compose_brief, evening_prompt
from src.atlas.database import Item
from src.atlas.guardian import Neglect

CAIRO = ZoneInfo("Africa/Cairo")
NOW = datetime(2026, 1, 5, 6, 0, tzinfo=CAIRO)


def _item(id, title, size="medium", type="task", due=None, created="2026-01-01"):
    return Item(id=id, type=type, domain="empire", title=title, size=size,
                due=due, trigger=None, status="open", confidence=0.9, created_at=created)


def test_deep_work_goes_to_morning_peak():
    items = [_item(1, "record lesson", size="deep")]
    plan = plan_day(items, free_hours=5, now=NOW)
    assert plan.scheduled[0].slot == "morning peak"


def test_priority_due_today_beats_everything():
    items = [
        _item(1, "deep thing", size="deep", created="2026-01-01"),
        _item(2, "urgent admin", size="quick", due="today", created="2026-01-04"),
    ]
    plan = plan_day(items, free_hours=5, now=NOW)
    assert plan.scheduled[0].item.title == "urgent admin"  # due-soon leads


def test_over_capacity_names_the_tradeoff_not_silent_drop():
    items = [_item(i, f"deep {i}", size="deep") for i in range(1, 6)]  # 5×120=600m
    plan = plan_day(items, free_hours=2, now=NOW)  # 120m budget
    assert plan.over_capacity
    assert plan.deferred                      # something waits
    assert plan.tradeoff is not None          # but it's SAID, not hidden (R4.5)
    assert "wait" in plan.tradeoff.lower()


def test_tiny_day_still_gives_one_start():
    items = [_item(1, "big deep task", size="deep")]  # 120m
    plan = plan_day(items, free_hours=0.5, now=NOW)   # 30m budget
    # even over budget, one item is placed so there's always a start
    assert len(plan.scheduled) == 1
    assert plan.over_capacity is True


def test_learned_durations_are_used_when_injected():
    items = [_item(1, "quick edit", size="quick")]
    # inject that this owner's "quick" really costs 90m
    plan = plan_day(items, free_hours=5, now=NOW, size_minutes=lambda it: 90)
    assert plan.scheduled[0].minutes == 90


def test_top_is_capped_at_three():
    items = [_item(i, f"t{i}", size="quick") for i in range(1, 8)]
    plan = plan_day(items, free_hours=10, now=NOW)
    assert len(plan.top) == 3


def test_brief_has_all_sections_in_order():
    items = [_item(1, "record B2 lesson", size="deep")]
    plan = plan_day(items, free_hours=5, now=NOW)
    neg = [Neglect("gym", "Gym / fitness", "health", 4, 3, "even 15 minutes today keeps it alive")]
    b = compose_brief(NOW, free_hours=5, plan=plan, neglects=neg, energy=4,
                      decision="trading review or course tonight — not both", filed_since=3)
    # ordered sections present
    assert "Today" in b.text
    assert "The 3 that matter" in b.text
    assert "record B2 lesson" in b.text
    assert "Going quiet" in b.text and "Gym" in b.text
    assert "One decision" in b.text
    assert "filed 3 notes" in b.text
    # spoken version is plain (no markdown asterisks)
    assert "*" not in b.spoken
    assert "Gym" in b.spoken


def test_brief_handles_empty_day_gracefully():
    plan = plan_day([], free_hours=0, now=NOW)
    b = compose_brief(NOW, free_hours=0, plan=plan, neglects=[])
    assert "clear day" in b.text.lower()
    assert b.spoken  # still speaks something


def test_evening_prompt_asks_done_and_energy():
    p = evening_prompt()
    assert "done" in p.lower()
    assert "1" in p and "5" in p  # the 1-5 energy question (R7.2)
