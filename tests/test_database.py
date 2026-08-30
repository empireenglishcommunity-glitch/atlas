from datetime import timedelta

from src.atlas.database import Database


def test_init_seeds_domains_once(at):
    d = Database(":memory:")
    d.init_db(seed=True, now=at())
    first = {x.name for x in d.active_domains()}
    assert "gym" in first and "empire" in first
    # re-seed is idempotent — never duplicates or overwrites
    d.seed_domains(now=at())
    assert {x.name for x in d.active_domains()} == first


def test_health_domains_get_3_day_threshold(db):
    assert db.get_domain("gym").neglect_days == 3
    assert db.get_domain("deen").neglect_days == 3
    assert db.get_domain("empire").neglect_days == 7


def test_capture_persisted_before_processing(db, at):
    cid = db.add_capture("voice", raw_text="", audio_path="/x.oga", now=at())
    # it exists and is unprocessed the instant it lands (R1.5)
    rows = db.unprocessed_captures()
    assert len(rows) == 1 and rows[0]["id"] == cid
    assert rows[0]["status"] == "unprocessed"
    # transcript arrives later, then processed
    db.set_capture_text(cid, "sagel el lesson")
    db.mark_capture(cid, "processed", understood_json="{}")
    assert db.unprocessed_captures() == []


def test_add_and_retire_domain_keeps_history(db, at):
    db.add_domain("podcast", "Podcast", kind="work", now=at())
    assert "podcast" in db.domain_names()
    # file an item under it
    db.save_item(None, "task", "record ep 1", domain="podcast", now=at())
    # retire → disappears from active list but history survives (R3.3)
    db.retire_domain("podcast")
    assert "podcast" not in db.domain_names()
    assert db.get_item(1).domain == "podcast"
    # re-adding reactivates without wiping history
    db.add_domain("podcast", "Podcast", kind="work", now=at())
    assert "podcast" in db.domain_names()


def test_set_neglect_days_tunable(db):
    db.set_neglect_days("gym", 2)
    assert db.get_domain("gym").neglect_days == 2


def test_last_attention_tracks_items_and_ledger(db, at):
    t0 = at(h=8)
    db.save_item(None, "task", "leg day", domain="gym", now=t0)
    assert db.last_attention("gym") == t0
    # a later ledger entry moves the marker forward
    t1 = at(h=18)
    db.record_ledger("gym", "completed", minutes=60, now=t1)
    assert db.last_attention("gym") == t1
    # a domain never touched has no attention
    assert db.last_attention("investing") is None


def test_domain_minutes_since_sums_ledger(db, at):
    base = at(h=6)
    db.record_ledger("empire", "worked", minutes=30, now=base)
    db.record_ledger("empire", "worked", minutes=45, now=at(h=12))
    db.record_ledger("trading", "worked", minutes=20, now=at(h=13))
    assert db.domain_minutes_since("empire", base - timedelta(hours=1)) == 75
    assert db.domain_minutes_since("trading", base - timedelta(hours=1)) == 20


def test_item_durations_for_size_learning(db, at):
    # two completed "quick" empire tasks that actually took a while
    i1 = db.save_item(None, "task", "quick edit", domain="empire", size="quick", now=at())
    i2 = db.save_item(None, "task", "quick fix", domain="empire", size="quick", now=at())
    db.record_ledger("empire", "completed", item_id=i1, minutes=80, now=at())
    db.record_ledger("empire", "completed", item_id=i2, minutes=95, now=at())
    durations = db.item_durations("empire", "quick")
    assert sorted(durations) == [80, 95]


def test_feelings_upsert_by_day(db, at):
    db.save_feeling("2026-01-01", energy=3, mood=4, now=at())
    db.save_feeling("2026-01-01", energy=2, mood=2, note="tired", now=at())  # same day overwrites
    rows = db.recent_feelings()
    assert len(rows) == 1
    assert rows[0]["energy"] == 2 and rows[0]["note"] == "tired"


def test_settings_roundtrip(db):
    assert db.get_setting("free_hours_default", "5") == "5"
    db.set_setting("free_hours_default", "3")
    assert db.get_setting("free_hours_default") == "3"
