"""Voice-note transcription (R1.2).

Thin, injectable wrapper. The transcript is treated as a NOISY signal — the
understanding layer corrects it by meaning, and the original audio is always kept,
so a bad transcript is recoverable (R2.4).
"""
from __future__ import annotations

from typing import Protocol


class Transcriber(Protocol):
    def transcribe(self, audio_path: str) -> str: ...


def transcribe(audio_path: str, client: Transcriber) -> str:
    """Return best-effort text for a voice note; empty string on failure (never raises)."""
    try:
        return (client.transcribe(audio_path) or "").strip()
    except Exception:
        return ""
