"""Tests for the pure client helpers (no SDK / network needed)."""
from src.atlas.clients import groq_audio_filename


def test_telegram_oga_becomes_ogg():
    # the live bug: Telegram voice notes are .oga, which Groq Whisper 400s on
    assert groq_audio_filename("/app/data/audio_cache/cap-123.oga") == "cap-123.ogg"


def test_opus_becomes_ogg():
    assert groq_audio_filename("/tmp/note.opus") == "note.ogg"


def test_accepted_extensions_pass_through():
    assert groq_audio_filename("/x/a.mp3") == "a.mp3"
    assert groq_audio_filename("/x/a.wav") == "a.wav"
    assert groq_audio_filename("/x/a.m4a") == "a.m4a"


def test_strips_directory_and_lowercases():
    assert groq_audio_filename("/deep/path/CAP-9.OGA") == "CAP-9.ogg"
