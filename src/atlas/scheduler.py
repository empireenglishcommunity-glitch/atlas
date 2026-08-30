"""Scheduled jobs (R4.1, R6.5, R7) — Africa/Cairo.

Runs the four background loops that make Atlas a secretary rather than a notepad:
the 06:00 morning brief, the 21:00 evening close, an hourly guardian sweep (so the
brief is current and neglect is caught even on absent days), and a 15-minute retry
of any capture stranded while a service was down.

Kept thin: each job delegates to a plain function so the logic is testable and the
scheduler is just wiring. APScheduler is a runtime dependency (not imported by tests).
"""
from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from . import capture, ledger, guardian
from .allocator import plan_day
from .brief import compose_brief, evening_prompt

log = logging.getLogger("atlas.scheduler")


def build_scheduler(ctx) -> AsyncIOScheduler:
    """Wire the four loops against an AtlasContext (see bot.py)."""
    sched = AsyncIOScheduler(timezone=ctx.settings.tz)

    async def morning_brief():
        try:
            await send_morning_brief(ctx)
        except Exception:
            log.exception("morning_brief failed")

    async def evening_close():
        try:
            await ctx.send_text(evening_prompt())
            ctx.db.set_setting("awaiting_close", ctx.settings.now().date().isoformat())
        except Exception:
            log.exception("evening_close failed")

    async def guardian_sweep():
        # touch nothing; just log so state/lag is observable. The brief reads live.
        try:
            n = guardian.neglected(ctx.db, ctx.settings.now())
            log.info("guardian: %d domain(s) going quiet", len(n))
        except Exception:
            log.exception("guardian_sweep failed")

    async def retry_unprocessed():
        try:
            resolved = capture.retry_unprocessed(
                ctx.db, ctx.llm, archive_dir=ctx.settings.archive_dir,
                now=ctx.settings.now())
            if resolved:
                log.info("retry: resolved %d stranded capture(s)", resolved)
        except Exception:
            log.exception("retry_unprocessed failed")

    tz = ctx.settings.tz
    sched.add_job(morning_brief, CronTrigger(hour=ctx.settings.brief_hour, minute=0, timezone=tz),
                  id="morning_brief")
    sched.add_job(evening_close, CronTrigger(hour=ctx.settings.evening_close_hour, minute=0, timezone=tz),
                  id="evening_close")
    sched.add_job(guardian_sweep, CronTrigger(minute=0, timezone=tz), id="guardian_sweep")
    sched.add_job(retry_unprocessed, CronTrigger(minute="*/15", timezone=tz), id="retry_unprocessed")
    return sched


async def send_morning_brief(ctx) -> None:
    """Compose + send the brief as written text AND a spoken voice note (R4)."""
    now = ctx.settings.now()
    free_hours = float(ctx.db.get_setting("free_hours_default", "5") or "5")

    open_items = ctx.db.open_items()
    plan = plan_day(
        open_items, free_hours=free_hours, now=now,
        chronotype=ctx.settings.chronotype,
        size_minutes=lambda it: ledger.learned_size_minutes(
            ctx.db, it.domain or "", it.size or "medium"),
    )
    neg = guardian.neglected(ctx.db, now)

    # how many notes were filed since yesterday's brief (reconciliation, R8.1)
    filed = _filed_since_last_brief(ctx, now)

    # energy from the most recent evening check-in, if any
    energy = _latest_energy(ctx)

    brief = compose_brief(now, free_hours=free_hours, plan=plan, neglects=neg,
                          energy=energy, filed_since=filed)

    await ctx.send_markdown(brief.text)

    # spoken version — degrade to text-only if Kokoro is down (R4.7)
    path = ctx.render_voice(brief.spoken, now)
    if path:
        await ctx.send_audio(path, title="Morning brief")
    ctx.db.set_setting("last_brief", now.isoformat())


def _filed_since_last_brief(ctx, now: datetime) -> int:
    last = ctx.db.get_setting("last_brief", "")
    with ctx.db._conn() as c:
        if last:
            r = c.execute("SELECT COUNT(*) n FROM items WHERE created_at>?", (last,)).fetchone()
        else:
            r = c.execute("SELECT COUNT(*) n FROM items").fetchone()
    return int(r["n"] or 0)


def _latest_energy(ctx):
    rows = ctx.db.recent_feelings(days=1)
    if rows and rows[0]["energy"] is not None:
        return int(rows[0]["energy"])
    return None
