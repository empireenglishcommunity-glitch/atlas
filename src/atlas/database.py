"""All SQLite access for Atlas.

Single-user, low volume, so a connection-per-operation model (open → act → close)
is simplest and safe — the ecosystem's proven SQLite pattern. Timestamps are stored
as timezone-aware ISO 8601 strings; callers pass an explicit `at`/`now` where it
matters, which keeps time-dependent logic deterministic under test.

Raw captures are always persisted BEFORE interpretation (R1.5/R9.5), so a downstream
failure can never lose the owner's input.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

from . import config as cfg

_SCHEMA = """
CREATE TABLE IF NOT EXISTS domains (
    name          TEXT PRIMARY KEY,
    label         TEXT NOT NULL,
    kind          TEXT NOT NULL DEFAULT 'work',
    neglect_days  INTEGER NOT NULL DEFAULT 7,
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS captures (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TEXT NOT NULL,
    source          TEXT NOT NULL,
    raw_text        TEXT,
    audio_path      TEXT,
    image_path      TEXT,
    status          TEXT NOT NULL DEFAULT 'unprocessed',
    understood_json TEXT
);

CREATE TABLE IF NOT EXISTS items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    capture_id   INTEGER REFERENCES captures(id),
    created_at   TEXT NOT NULL,
    type         TEXT NOT NULL,
    domain       TEXT,
    title        TEXT NOT NULL,
    size         TEXT,
    due          TEXT,
    trigger      TEXT,
    status       TEXT NOT NULL DEFAULT 'open',
    confidence   REAL
);

CREATE TABLE IF NOT EXISTS ledger (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    at         TEXT NOT NULL,
    domain     TEXT,
    item_id    INTEGER REFERENCES items(id),
    kind       TEXT NOT NULL,
    minutes    INTEGER,
    note       TEXT
);

CREATE TABLE IF NOT EXISTS feelings (
    day        TEXT PRIMARY KEY,
    energy     INTEGER,
    mood       INTEGER,
    note       TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
CREATE INDEX IF NOT EXISTS idx_items_domain ON items(domain);
CREATE INDEX IF NOT EXISTS idx_ledger_domain_at ON ledger(domain, at);
CREATE INDEX IF NOT EXISTS idx_captures_status ON captures(status);
"""


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


# ── dataclasses returned to the rest of the system ────────────────────────────
@dataclass
class Domain:
    name: str
    label: str
    kind: str
    neglect_days: int
    active: bool
    created_at: str = ""


@dataclass
class Item:
    id: int
    type: str
    domain: Optional[str]
    title: str
    size: Optional[str]
    due: Optional[str]
    trigger: Optional[str]
    status: str
    confidence: Optional[float]
    created_at: str


class Database:
    """Owns the SQLite file and every read/write against it."""

    def __init__(self, path: str = "data/atlas.db"):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        # :memory: needs a single shared connection to persist across calls
        self._mem_conn = sqlite3.connect(path) if path == ":memory:" else None
        if self._mem_conn is not None:
            self._mem_conn.row_factory = sqlite3.Row

    @contextmanager
    def _conn(self):
        if self._mem_conn is not None:
            yield self._mem_conn
            self._mem_conn.commit()
            return
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ── init + seed ───────────────────────────────────────────────────────────
    def init_db(self, seed: bool = True, now: Optional[datetime] = None) -> None:
        with self._conn() as c:
            c.executescript(_SCHEMA)
        if seed:
            self.seed_domains(now=now)

    def seed_domains(self, now: Optional[datetime] = None) -> None:
        """Insert the seed domains only if none exist (idempotent, never overwrites)."""
        ts = _iso(now or datetime.now())
        with self._conn() as c:
            existing = c.execute("SELECT COUNT(*) AS n FROM domains").fetchone()["n"]
            if existing:
                return
            for d in cfg.SEED_DOMAINS:
                c.execute(
                    "INSERT INTO domains(name,label,kind,neglect_days,active,created_at) "
                    "VALUES(?,?,?,?,1,?)",
                    (d["name"], d["label"], d["kind"],
                     cfg.neglect_days_for(d["kind"]), ts),
                )

    # ── domains (R3) ────────────────────────────────────────────────────────
    def add_domain(self, name: str, label: str, kind: str = "work",
                   neglect_days: Optional[int] = None,
                   now: Optional[datetime] = None) -> None:
        nd = neglect_days if neglect_days is not None else cfg.neglect_days_for(kind)
        ts = _iso(now or datetime.now())
        with self._conn() as c:
            # re-activating a previously retired domain keeps its history
            c.execute(
                "INSERT INTO domains(name,label,kind,neglect_days,active,created_at) "
                "VALUES(?,?,?,?,1,?) "
                "ON CONFLICT(name) DO UPDATE SET active=1,label=excluded.label,kind=excluded.kind",
                (name, label, kind, nd, ts),
            )

    def retire_domain(self, name: str) -> None:
        """Deactivate a domain WITHOUT deleting its history (R3.3/R3.4)."""
        with self._conn() as c:
            c.execute("UPDATE domains SET active=0 WHERE name=?", (name,))

    def rename_domain(self, name: str, new_label: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE domains SET label=? WHERE name=?", (new_label, name))

    def set_neglect_days(self, name: str, days: int) -> None:
        with self._conn() as c:
            c.execute("UPDATE domains SET neglect_days=? WHERE name=?", (days, name))

    def get_domain(self, name: str) -> Optional[Domain]:
        with self._conn() as c:
            r = c.execute("SELECT * FROM domains WHERE name=?", (name,)).fetchone()
        return _row_to_domain(r) if r else None

    def active_domains(self) -> list[Domain]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM domains WHERE active=1 ORDER BY kind,name"
            ).fetchall()
        return [_row_to_domain(r) for r in rows]

    def domain_names(self) -> list[str]:
        return [d.name for d in self.active_domains()]

    # ── captures (R1) ─────────────────────────────────────────────────────────
    def add_capture(self, source: str, raw_text: str = "", audio_path: str = "",
                    image_path: str = "", now: Optional[datetime] = None) -> int:
        ts = _iso(now or datetime.now())
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO captures(created_at,source,raw_text,audio_path,image_path,status)"
                " VALUES(?,?,?,?,?,'unprocessed')",
                (ts, source, raw_text, audio_path, image_path),
            )
            return int(cur.lastrowid)

    def set_capture_text(self, capture_id: int, text: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE captures SET raw_text=? WHERE id=?", (text, capture_id))

    def mark_capture(self, capture_id: int, status: str,
                     understood_json: str = "") -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE captures SET status=?, understood_json=? WHERE id=?",
                (status, understood_json, capture_id),
            )

    def unprocessed_captures(self, limit: int = 20) -> list[sqlite3.Row]:
        with self._conn() as c:
            return c.execute(
                "SELECT * FROM captures WHERE status='unprocessed' ORDER BY id LIMIT ?",
                (limit,),
            ).fetchall()

    # ── items (R2) ────────────────────────────────────────────────────────────
    def save_item(self, capture_id: Optional[int], type: str, title: str,
                  domain: Optional[str] = None, size: Optional[str] = None,
                  due: Optional[str] = None, trigger: Optional[str] = None,
                  confidence: Optional[float] = None,
                  now: Optional[datetime] = None) -> int:
        ts = _iso(now or datetime.now())
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO items(capture_id,created_at,type,domain,title,size,due,"
                "trigger,status,confidence) VALUES(?,?,?,?,?,?,?,?,'open',?)",
                (capture_id, ts, type, domain, title, size, due, trigger, confidence),
            )
            return int(cur.lastrowid)

    def open_items(self, type: Optional[str] = None) -> list[Item]:
        q = "SELECT * FROM items WHERE status='open'"
        args: tuple = ()
        if type:
            q += " AND type=?"
            args = (type,)
        q += " ORDER BY created_at"
        with self._conn() as c:
            rows = c.execute(q, args).fetchall()
        return [_row_to_item(r) for r in rows]

    def set_item_status(self, item_id: int, status: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE items SET status=? WHERE id=?", (status, item_id))

    def get_item(self, item_id: int) -> Optional[Item]:
        with self._conn() as c:
            r = c.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        return _row_to_item(r) if r else None

    # ── ledger (R5) ───────────────────────────────────────────────────────────
    def record_ledger(self, domain: Optional[str], kind: str,
                      item_id: Optional[int] = None, minutes: Optional[int] = None,
                      note: str = "", now: Optional[datetime] = None) -> int:
        ts = _iso(now or datetime.now())
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO ledger(at,domain,item_id,kind,minutes,note) VALUES(?,?,?,?,?,?)",
                (ts, domain, item_id, kind, minutes, note),
            )
            return int(cur.lastrowid)

    def last_attention(self, domain: str) -> Optional[datetime]:
        """Most recent moment a domain got attention — a ledger entry OR an item created."""
        with self._conn() as c:
            r = c.execute(
                "SELECT MAX(at) AS t FROM ("
                "  SELECT at FROM ledger WHERE domain=? "
                "  UNION ALL "
                "  SELECT created_at AS at FROM items WHERE domain=?"
                ")",
                (domain, domain),
            ).fetchone()
        return _parse(r["t"]) if r and r["t"] else None

    def domain_minutes_since(self, domain: str, since: datetime) -> int:
        with self._conn() as c:
            r = c.execute(
                "SELECT COALESCE(SUM(minutes),0) AS m FROM ledger "
                "WHERE domain=? AND at>=?",
                (domain, _iso(since)),
            ).fetchone()
        return int(r["m"] or 0)

    def item_durations(self, domain: str, size: str) -> list[int]:
        """Real minutes for completed items of a given domain+size — feeds size-learning."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT l.minutes AS m FROM ledger l JOIN items i ON l.item_id=i.id "
                "WHERE i.domain=? AND i.size=? AND l.minutes IS NOT NULL",
                (domain, size),
            ).fetchall()
        return [int(r["m"]) for r in rows]

    # ── feelings (R7) ─────────────────────────────────────────────────────────
    def save_feeling(self, day: str, energy: Optional[int] = None,
                     mood: Optional[int] = None, note: str = "",
                     now: Optional[datetime] = None) -> None:
        ts = _iso(now or datetime.now())
        with self._conn() as c:
            c.execute(
                "INSERT INTO feelings(day,energy,mood,note,created_at) VALUES(?,?,?,?,?) "
                "ON CONFLICT(day) DO UPDATE SET energy=excluded.energy,"
                "mood=excluded.mood,note=excluded.note",
                (day, energy, mood, note, ts),
            )

    def recent_feelings(self, days: int = 7) -> list[sqlite3.Row]:
        with self._conn() as c:
            return c.execute(
                "SELECT * FROM feelings ORDER BY day DESC LIMIT ?", (days,)
            ).fetchall()

    # ── settings / flags ──────────────────────────────────────────────────────
    def set_setting(self, key: str, value: str) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def get_setting(self, key: str, default: str = "") -> str:
        with self._conn() as c:
            r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default


def _row_to_domain(r: sqlite3.Row) -> Domain:
    return Domain(name=r["name"], label=r["label"], kind=r["kind"],
                  neglect_days=int(r["neglect_days"]), active=bool(r["active"]),
                  created_at=r["created_at"])


def _row_to_item(r: sqlite3.Row) -> Item:
    return Item(id=int(r["id"]), type=r["type"], domain=r["domain"], title=r["title"],
                size=r["size"], due=r["due"], trigger=r["trigger"], status=r["status"],
                confidence=r["confidence"], created_at=r["created_at"])
