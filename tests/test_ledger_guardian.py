"""Ledger + Guardian tests. Deterministic time via the `at` fixture."""
from __future__ import annotations

from datetime import timedelta

from src.atlas import ledger, guardian


# ── ledger ────────────────────────────────────────────────────────────────────
def test_log_completion_marks_done_and_records(db, at):
    iid = db.save_item(None, "task", "record lesson", domain="empire",
                       size="deep", now=at())
    ledger.log_completion(db, iid, minutes=90, now=at(h=11))
    assert db.get_item(iid).status == "done"
    # attention shows up for empire
    rep = {a.domain: a for a in ledger.attention_report(db, now=at(h=12))}
    assert rep["empire"].minutes == 90
    assert rep["empire"].items_touched == 1


def test_attention_report_covers_all_active_domains(db, at):
    rep = ledger.attention_report(db, now=at())
    names = {a.domain for a in rep}
    assert "gym" in names and "empire" in names
    # nothing logged yet → zero minutes
    assert all(a.minutes == 0 for a in rep)


def test_learned_size_uses_history_when_enough(db, at):
    # owner's "quick" empire tasks really take ~80-100 min
    for m in (80, 100, 90, 120):
        iid = db.save_item(None, "task", "quick thing", domain="empire",
                           size="quick", now=at())
        ledger.log_completion(db, iid, minutes=m, now=at())
    # with >=3 samples, Atlas stops trusting the 15-min default (R5.3)
    est = ledger.learned_size_minutes(db, "empire", "quick")
    assert est >= 80


def test_learned_size_falls_back_without_history(db):
    assert ledger.learned_size_minutes(db, "trading", "deep") == 120  # generic default


# ── guardian ──────────────────────────────────────────────────────────────────
def test_no_alarms_when_everything_fresh(db, at):
    # touch every domain today
    for name in db.domain_names():
        db.record_ledger(name, "worked", minutes=10, now=at())
    assert guardian.neglected(db, now=at(h=20)) == []


def test_health_alarms_at_3_days_work_does_not(db, at):
    start = at(d=1)
    # touch gym (health, 3d) and empire (work, 7d) on day 1
    db.record_ledger("gym", "worked", minutes=30, now=start)
    db.record_ledger("empire", "worked", minutes=30, now=start)
    # 4 days later: gym is overdue (>=3), empire is not (<7)
    now = start + timedelta(days=4)
    flags = {n.domain: n for n in guardian.neglected(db, now=now)}
    assert "gym" in flags
    assert "empire" not in flags
    assert flags["gym"].silent_days == 4
    assert "15 minutes" in flags["gym"].suggested_action  # concrete action, not guilt


def test_work_alarms_after_7_days(db, at):
    start = at(d=1)
    db.record_ledger("empire", "worked", minutes=30, now=start)
    now = start + timedelta(days=8)
    flags = {n.domain: n for n in guardian.neglected(db, now=now)}
    assert "empire" in flags and flags["empire"].silent_days == 8


def test_new_domain_not_instantly_neglected(db, at):
    # add a domain today; it must not alarm before its threshold elapses
    db.add_domain("podcast", "Podcast", kind="work", now=at(d=1))
    same_day = guardian.neglected(db, now=at(d=1, h=23))
    assert all(n.domain != "podcast" for n in same_day)
    # but it DOES alarm once 7 quiet days pass since creation
    later = guardian.neglected(db, now=at(d=1) + timedelta(days=8))
    assert any(n.domain == "podcast" for n in later)


def test_retired_domain_raises_no_alarm(db, at):
    start = at(d=1)
    db.record_ledger("deen", "worked", minutes=10, now=start)
    db.retire_domain("deen")
    now = start + timedelta(days=30)
    assert all(n.domain != "deen" for n in guardian.neglected(db, now=now))


def test_alarms_sorted_worst_first(db, at):
    start = at(d=1)
    # touch all three health domains on day 1 so none alarm from their creation baseline
    for name in ("gym", "diet", "deen"):
        db.record_ledger(name, "worked", minutes=10, now=start)
    # keep diet + deen fresh at day 6; leave gym untouched
    db.record_ledger("diet", "worked", minutes=10, now=start + timedelta(days=6))
    db.record_ledger("deen", "worked", minutes=10, now=start + timedelta(days=6))
    # day 10: gym silent 10 (overrun 7), diet/deen silent 4 (overrun 1)
    now = start + timedelta(days=10)
    flags = guardian.neglected(db, now=now)
    assert flags[0].domain == "gym"   # biggest overrun leads
