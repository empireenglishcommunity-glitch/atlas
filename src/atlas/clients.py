"""Real service adapters (Groq LLM + Groq Whisper).

Kept in one place and imported only at runtime (from bot.py), so the pure-logic
modules and their tests never need the `groq` package or a network. Each adapter
implements the minimal Protocol the logic layer expects.
"""
from __future__ import annotations

from .config import Settings


class GroqLLM:
    """Implements understand.LLMClient.complete() using Groq chat completions."""

    def __init__(self, settings: Settings):
        from groq import Groq  # lazy import — only needed at runtime
        self._client = Groq(api_key=settings.groq_api_key)
        self._model = settings.groq_model

    def complete(self, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,          # low: classification, not creativity
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content or ""


class HttpAudioPoster:
    """Implements voice.AudioPoster — POSTs to Kokoro and returns raw audio bytes."""

    def __init__(self, timeout: float = 60.0):
        self._timeout = timeout

    def post_audio(self, url: str, payload: dict) -> bytes:
        import httpx  # lazy — runtime only
        r = httpx.post(url, json=payload, timeout=self._timeout)
        r.raise_for_status()
        return r.content


class GroqTranscriber:
    """Implements transcribe.Transcriber using Groq Whisper."""

    def __init__(self, settings: Settings):
        from groq import Groq
        self._client = Groq(api_key=settings.groq_api_key)
        self._model = settings.groq_whisper_model

    def transcribe(self, audio_path: str) -> str:
        with open(audio_path, "rb") as f:
            resp = self._client.audio.transcriptions.create(
                file=(audio_path, f.read()),
                model=self._model,
                # no forced language: the owner code-switches Arabic/English
            )
        return (getattr(resp, "text", "") or "").strip()
