"""Shared fixtures. Tests never touch the network or real credentials."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.atlas.database import Database

CAIRO = ZoneInfo("Africa/Cairo")


@pytest.fixture
def db() -> Database:
    """A fresh in-memory database, schema initialised, domains seeded."""
    d = Database(":memory:")
    d.init_db(seed=True, now=datetime(2026, 1, 1, tzinfo=CAIRO))
    return d


@pytest.fixture
def at():
    """Helper to build Cairo-aware timestamps in tests."""
    def _make(y=2026, mo=1, d=1, h=9, mi=0):
        return datetime(y, mo, d, h, mi, tzinfo=CAIRO)
    return _make
