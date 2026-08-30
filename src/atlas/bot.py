"""Atlas bot — the Telegram surface + wiring (R1, R7, R8). Runtime entrypoint.

Everything Atlas *is* lives in the tested logic modules; this file is the thin
adapter that turns Telegram updates into `capture.ingest(...)` calls and sends the
brief. It talks ONLY to the owner (R1.6/R9.2). Heavy deps (telegram, apscheduler)
are runtime-only, so the test suite never imports this module.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          MessageHandler, filters)

from . import capture, ledger, voice
from .clients import GroqLLM, GroqTranscriber, HttpAudioPoster
from .config import Settings, load_settings
from .database import Database
from .scheduler import build_scheduler, send_morning_brief
from .transcribe import transcribe

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("atlas.bot")

AUDIO_DIR = "data/audio_cache"


@dataclass
class AtlasContext:
    """Everything the jobs + handlers need, with Telegram send helpers."""
    settings: Settings
    db: Database
    llm: object
    transcriber: object
    poster: object
    bot: object = None  # set after the Application is built

    # ── outbound helpers (owner-only) ──
    async def send_text(self, text: str) -> None:
        await self.bot.send_message(self.settings.owner_chat_id, text)

    async def send_markdown(self, text: str) -> None:
        try:
            await self.bot.send_message(self.settings.owner_chat_id, text,
                                        parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await self.bot.send_message(self.settings.owner_chat_id, text)

    async def send_audio(self, path: str, title: str = "Atlas") -> None:
        with open(path, "rb") as f:
            await self.bot.send_audio(self.settings.owner_chat_id, audio=f, title=title)

    def render_voice(self, text: str, now: datetime) -> Optional[str]:
        out = str(Path(AUDIO_DIR) / f"brief-{now.strftime('%Y%m%d')}.mp3")
        return voice.speak(text, out, self.poster,
                           kokoro_url=self.settings.kokoro_url,
                           voice=self.settings.kokoro_voice)


# ── owner guard ────────────────────────────────────────────────────────────────
def _is_owner(ctx: AtlasContext, update: Update) -> bool:
    return bool(update.effective_chat and update.effective_chat.id == ctx.settings.owner_chat_id)


# ── handlers ─────────────────────────────────────────────────────────────────
async def on_text(update, tg_ctx, *, actx: AtlasContext):
    if not _is_owner(actx, update):
        return
    text = (update.message.text or "").strip()

    # evening close answer? (R7)
    if actx.db.get_setting("awaiting_close", "") == actx.settings.now().date().isoformat():
        _record_close(actx, text)
        actx.db.set_setting("awaiting_close", "")
        await update.message.reply_text("🌙 Logged. Rest well — I've got tomorrow.")
        return

    res = capture.ingest(actx.db, actx.llm, source="text", text=text,
                         archive_dir=actx.settings.archive_dir, now=actx.settings.now())
    await update.message.reply_text(res.confirmation)


async def on_voice(update, tg_ctx, *, actx: AtlasContext):
    if not _is_owner(actx, update):
        return
    await tg_ctx.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
    Path(AUDIO_DIR).mkdir(parents=True, exist_ok=True)
    tgfile = await update.message.voice.get_file()
    path = str(Path(AUDIO_DIR) / f"cap-{update.message.message_id}.oga")
    await tgfile.download_to_drive(path)

    text = transcribe(path, actx.transcriber)   # noisy signal; understood by meaning
    res = capture.ingest(actx.db, actx.llm, source="voice", text=text, audio_path=path,
                         archive_dir=actx.settings.archive_dir, now=actx.settings.now())
    await update.message.reply_text(res.confirmation)


async def on_photo(update, tg_ctx, *, actx: AtlasContext):
    if not _is_owner(actx, update):
        return
    Path(AUDIO_DIR).mkdir(parents=True, exist_ok=True)
    photo = update.message.photo[-1]
    tgfile = await photo.get_file()
    path = str(Path(AUDIO_DIR) / f"img-{update.message.message_id}.jpg")
    await tgfile.download_to_drive(path)
    caption = (update.message.caption or "").strip()
    res = capture.ingest(actx.db, actx.llm, source="photo", text=caption, image_path=path,
                         archive_dir=actx.settings.archive_dir, now=actx.settings.now())
    await update.message.reply_text(res.confirmation)


async def cmd_start(update, tg_ctx, *, actx: AtlasContext):
    if not _is_owner(actx, update):
        return
    await update.message.reply_text(
        "👋 Atlas is on. Talk to me any time — type, forward, or send a voice note. "
        "I'll file it, watch what's slipping, and brief you at 6 AM.\n\n"
        "Commands: /today  /domains  /hours <n>  /done <id> [minutes]  /addomain <name> | <label>"
    )


async def cmd_today(update, tg_ctx, *, actx: AtlasContext):
    if not _is_owner(actx, update):
        return
    await send_morning_brief(actx)   # on-demand brief


async def cmd_domains(update, tg_ctx, *, actx: AtlasContext):
    if not _is_owner(actx, update):
        return
    lines = [f"• {d.label} (`{d.name}`) — {d.kind}, alarms at {d.neglect_days}d"
             for d in actx.db.active_domains()]
    await update.message.reply_text("*Your domains:*\n" + "\n".join(lines),
                                    parse_mode=ParseMode.MARKDOWN)


async def cmd_hours(update, tg_ctx, *, actx: AtlasContext):
    if not _is_owner(actx, update):
        return
    m = re.search(r"(\d+(?:\.\d+)?)", " ".join(tg_ctx.args))
    if not m:
        await update.message.reply_text("Tell me a number, e.g. /hours 4")
        return
    actx.db.set_setting("free_hours_default", m.group(1))
    await update.message.reply_text(f"Got it — planning around ~{m.group(1)}h a day.")


async def cmd_done(update, tg_ctx, *, actx: AtlasContext):
    if not _is_owner(actx, update):
        return
    args = tg_ctx.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Which item? e.g. /done 12 90  (item 12, took 90 min)")
        return
    item_id = int(args[0])
    minutes = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
    if not actx.db.get_item(item_id):
        await update.message.reply_text("I don't see that item.")
        return
    ledger.log_completion(actx.db, item_id, minutes=minutes, now=actx.settings.now())
    await update.message.reply_text("✅ Done — logged." + (f" ({minutes}m)" if minutes else ""))


async def cmd_addomain(update, tg_ctx, *, actx: AtlasContext):
    if not _is_owner(actx, update):
        return
    raw = " ".join(tg_ctx.args)
    name, _, label = raw.partition("|")
    name = name.strip().lower().replace(" ", "_")
    label = label.strip() or name.replace("_", " ").title()
    if not name:
        await update.message.reply_text("Usage: /addomain trading | Trading & markets")
        return
    actx.db.add_domain(name, label, kind="work", now=actx.settings.now())
    await update.message.reply_text(f"Added domain *{label}* (`{name}`).",
                                    parse_mode=ParseMode.MARKDOWN)


# ── close parsing (R7) ─────────────────────────────────────────────────────────
def _record_close(actx: AtlasContext, text: str) -> None:
    now = actx.settings.now()
    # a trailing 1-5 is the energy answer; the rest is what got done
    energy = None
    m = re.search(r"\b([1-5])\b\s*$", text.strip())
    if m:
        energy = int(m.group(1))
        text = text[: m.start()].strip()
    if text:
        actx.db.record_ledger(None, "note", note=text, now=now)
    actx.db.save_feeling(now.date().isoformat(), energy=energy, note=text, now=now)


def _register(app: Application, actx: AtlasContext) -> None:
    def bind(fn):
        async def handler(update, tg_ctx):
            await fn(update, tg_ctx, actx=actx)
        return handler

    owner = filters.Chat(chat_id=actx.settings.owner_chat_id)
    app.add_handler(CommandHandler("start", bind(cmd_start), filters=owner))
    app.add_handler(CommandHandler("today", bind(cmd_today), filters=owner))
    app.add_handler(CommandHandler("domains", bind(cmd_domains), filters=owner))
    app.add_handler(CommandHandler("hours", bind(cmd_hours), filters=owner))
    app.add_handler(CommandHandler("done", bind(cmd_done), filters=owner))
    app.add_handler(CommandHandler("addomain", bind(cmd_addomain), filters=owner))
    app.add_handler(MessageHandler(owner & filters.VOICE, bind(on_voice)))
    app.add_handler(MessageHandler(owner & filters.PHOTO, bind(on_photo)))
    app.add_handler(MessageHandler(owner & filters.TEXT & ~filters.COMMAND, bind(on_text)))


def main() -> None:
    settings = load_settings()
    if not settings.telegram_bot_token or not settings.owner_chat_id:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN and OWNER_CHAT_ID in .env")

    db = Database(settings.db_path)
    db.init_db(seed=True, now=settings.now())

    actx = AtlasContext(
        settings=settings,
        db=db,
        llm=GroqLLM(settings),
        transcriber=GroqTranscriber(settings),
        poster=HttpAudioPoster(),
    )

    app = Application.builder().token(settings.telegram_bot_token).build()
    actx.bot = app.bot
    _register(app, actx)

    sched = build_scheduler(actx)

    async def _post_init(_app):
        sched.start()
        log.info("Atlas online — brief at %02d:00 %s", settings.brief_hour, settings.timezone)

    app.post_init = _post_init
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
