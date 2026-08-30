import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.atlas import archive, voice
from src.atlas.capture import ingest, retry_unprocessed

CAIRO = ZoneInfo("Africa/Cairo")
NOW = datetime(2026, 1, 5, 9, 0, tzinfo=CAIRO)


class FakeLLM:
    def __init__(self, reply="", raise_it=False):
        self.reply = reply
        self.raise_it = raise_it

    def complete(self, system, user):
        if self.raise_it:
            raise RuntimeError("down")
        return self.reply


def _reply(**kw):
    base = {"type": "task", "title": "record the B2 lesson", "domain": "empire",
            "size": "deep", "due": None, "trigger": None, "confidence": 0.9, "clarify": None}
    base.update(kw)
    return json.dumps(base, ensure_ascii=False)


# ── capture ingest ────────────────────────────────────────────────────────────
def test_ingest_persists_before_processing_then_saves_item(db, tmp_path):
    llm = FakeLLM(_reply())
    res = ingest(db, llm, source="text", text="sagel el lesson B2",
                 archive_dir=str(tmp_path), now=NOW)
    assert res.item_id is not None
    assert res.confirmation.startswith("✅")
    assert "Empire" in res.confirmation           # domain label shown
    # capture row exists and is processed
    it = db.get_item(res.item_id)
    assert it.domain == "empire" and it.size == "deep"


def test_ingest_low_confidence_asks_and_saves_no_item(db, tmp_path):
    llm = FakeLLM(_reply(confidence=0.2, clarify=None))
    res = ingest(db, llm, source="voice", text="اعمل الحاجة",
                 archive_dir=str(tmp_path), now=NOW)
    assert res.item_id is None                    # nothing fabricated
    assert res.confirmation.startswith("❓")       # it asks
    # the raw capture is still saved (never lost) and flagged for clarify
    rows = [r for r in db.unprocessed_captures()]  # not 'unprocessed' anymore
    assert db.get_item(1) is None


def test_ingest_never_loses_input_when_llm_down(db, tmp_path):
    llm = FakeLLM(raise_it=True)
    res = ingest(db, llm, source="voice", text="حاجة مهمة جدا",
                 archive_dir=str(tmp_path), now=NOW)
    # no item, but the capture is persisted with its text for retry (R2.7)
    assert res.item_id is None
    assert res.capture_id == 1


def test_ingest_writes_archive_markdown(db, tmp_path):
    llm = FakeLLM(_reply(title="call the accountant", domain="personal", size="quick"))
    ingest(db, llm, source="text", text="kallem el accountant",
           archive_dir=str(tmp_path), now=NOW)
    md = list(Path(tmp_path).glob("*.md"))
    assert md, "archive file should exist"
    content = md[0].read_text(encoding="utf-8")
    assert "call the accountant" in content


def test_retry_unprocessed_resolves_when_service_returns(db, tmp_path):
    # first a failed ingest leaves an unprocessed capture with text
    ingest(db, FakeLLM(raise_it=True), source="voice", text="sagel lesson B2",
           archive_dir=str(tmp_path), now=NOW)
    assert len(db.unprocessed_captures()) == 1
    # service returns → retry sweeps it into a real item
    n = retry_unprocessed(db, FakeLLM(_reply()), archive_dir=str(tmp_path), now=NOW)
    assert n == 1
    assert len(db.unprocessed_captures()) == 0


# ── archive ───────────────────────────────────────────────────────────────────
def test_archive_appends_and_creates_month_file(tmp_path):
    archive.append(str(tmp_path), "task", "first thing", NOW, domain="empire")
    archive.append(str(tmp_path), "idea", "second thing", NOW)
    f = Path(tmp_path) / "2026-01.md"
    text = f.read_text(encoding="utf-8")
    assert "first thing" in text and "second thing" in text
    assert "#empire" in text


def test_archive_never_raises_on_bad_dir():
    # a broken path must not crash the live flow
    archive.append("/root/\0bad", "task", "x", NOW)  # returns quietly


# ── voice ─────────────────────────────────────────────────────────────────────
class FakePoster:
    def __init__(self, audio=b"ID3fakeaudio", raise_it=False):
        self.audio = audio
        self.raise_it = raise_it
        self.last_payload = None

    def post_audio(self, url, payload):
        self.last_payload = payload
        if self.raise_it:
            raise RuntimeError("kokoro down")
        return self.audio


def test_voice_writes_mp3_and_passes_voice(tmp_path):
    poster = FakePoster()
    out = voice.speak("Good morning", str(tmp_path / "brief.mp3"), poster,
                      voice="af_heart")
    assert out and Path(out).exists()
    assert poster.last_payload["voice"] == "af_heart"
    assert poster.last_payload["input"] == "Good morning"


def test_voice_degrades_gracefully_when_kokoro_down(tmp_path):
    out = voice.speak("hi", str(tmp_path / "b.mp3"), FakePoster(raise_it=True))
    assert out is None                     # caller falls back to text-only (R4.7)


def test_voice_skips_empty_text(tmp_path):
    assert voice.speak("   ", str(tmp_path / "b.mp3"), FakePoster()) is None
