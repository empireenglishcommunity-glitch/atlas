"""Spoken brief via Kokoro TTS (R4.1) — the voice note that lands at 6 AM.

Kokoro runs on the box (localhost:8880) with an OpenAI-compatible endpoint. The
HTTP poster is injected so this is testable without a network, and it degrades
gracefully: if Kokoro is down the caller still sends the written brief (R4.7).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol


class AudioPoster(Protocol):
    def post_audio(self, url: str, payload: dict) -> bytes: ...


def speak(text: str, out_path: str, poster: AudioPoster,
          kokoro_url: str = "http://localhost:8880",
          voice: str = "af_heart") -> Optional[str]:
    """Render `text` to an mp3 at `out_path`. Returns the path, or None if TTS
    was unavailable (caller then sends text only)."""
    if not text.strip():
        return None
    url = f"{kokoro_url.rstrip('/')}/v1/audio/speech"
    payload = {"model": "kokoro", "input": text, "voice": voice,
               "response_format": "mp3", "speed": 1.0}
    try:
        audio = poster.post_audio(url, payload)
        if not audio:
            return None
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(audio)
        return out_path
    except Exception:
        return None  # graceful — never break the brief over a TTS hiccup
