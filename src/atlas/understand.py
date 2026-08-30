"""Understanding — turn a messy, code-switched capture into a structured record.

The owner speaks Egyptian Arabic mixed with English, often via a noisy voice
transcript (dialect ASR word-error-rate is high). So this layer is built on one
rule: **interpret by MEANING, not by literal words** (R2.4). It is given the live
domain list and known names as context, and it returns a strict JSON contract the
rest of Atlas trusts.

The LLM client is injected, so every test runs with a fake client — no network, no
key. (A green test is not proof the live LLM behaves; that is verified separately.)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Optional, Protocol

# The vocabulary Atlas understands (R2.1). "feeling"/"person"/"expense" are accepted
# now so future organs slot in without changing the contract.
ITEM_TYPES = {"task", "idea", "journal", "event", "feeling", "person", "expense"}
SIZES = {"quick", "medium", "deep"}
UNASSIGNED = "unassigned"

# below this, Atlas asks instead of guessing silently (R2.5)
CONFIDENCE_FLOOR = 0.5


@dataclass
class Understanding:
    """The structured result of interpreting one capture (the JSON contract)."""
    type: str
    title: str
    domain: Optional[str] = None
    size: Optional[str] = None
    due: Optional[str] = None
    trigger: Optional[str] = None
    confidence: float = 0.0
    clarify: Optional[str] = None      # a single short question, or None
    raw: Optional[str] = None          # original text, always retained
    retryable: bool = False            # True = a SERVICE failure, retry later (not owner ambiguity)

    @property
    def needs_clarification(self) -> bool:
        return bool(self.clarify)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    def confirmation_line(self, domain_label: str | None = None) -> str:
        """The 'understood as …' line the owner sees, to catch a misread instantly (R2.6)."""
        if self.needs_clarification:
            return f"❓ {self.clarify}"
        where = domain_label or self.domain or UNASSIGNED
        bits = [f"“{self.title}”", f"· {where}"]
        if self.type != "task":
            bits.append(f"· {self.type}")
        if self.size:
            bits.append(f"· {self.size}")
        if self.due:
            bits.append(f"· {self.due}")
        return "✅ Got it — " + " ".join(bits)


class LLMClient(Protocol):
    """Minimal shape Atlas needs from a chat client (Groq-compatible)."""
    def complete(self, system: str, user: str) -> str: ...


_SYSTEM = """You are Atlas, a personal life secretary. You receive a raw note from your \
owner. It may be in Egyptian Arabic, English, or a mix, and it may come from an imperfect \
voice transcript, so INTERPRET BY MEANING — fix obvious transcription noise using the \
context you are given, do not translate literally.

Classify the note into ONE JSON object with these exact keys:
- "type": one of task | idea | journal | event | feeling | person | expense
- "title": a short, clean rephrasing of the note in the note's own language (fix garbles)
- "domain": EXACTLY one name from the provided domain list, or "unassigned" if none fits
- "size": for a task, one of quick | medium | deep; else null
- "due": any time/date signal present (keep the owner's words), else null
- "trigger": an implementation-intention cue if implied ("after fajr", "morning peak"), else null
- "confidence": 0.0-1.0, how sure you are of type+domain
- "clarify": if confidence is low OR the note is ambiguous, ONE short question to ask the \
owner (in his language); otherwise null

Return ONLY the JSON object, nothing else."""


def _build_user_prompt(text: str, domains: list[tuple[str, str]],
                       names: list[str] | None) -> str:
    domain_lines = "\n".join(f"- {name}: {label}" for name, label in domains)
    known = ", ".join(names) if names else "(none provided)"
    return (
        f"Domain list (name: description):\n{domain_lines}\n\n"
        f"Known names/projects (for meaning-correction): {known}\n\n"
        f"Owner's note:\n{text}"
    )


def _extract_json(raw: str) -> dict:
    """Pull the JSON object out of an LLM reply, tolerating code fences / stray prose."""
    s = raw.strip()
    if s.startswith("```"):
        s = s.strip("`")
        # drop an optional leading 'json' language tag
        if "\n" in s:
            first, rest = s.split("\n", 1)
            if first.strip().lower() in {"json", ""}:
                s = rest
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found")
    return json.loads(s[start:end + 1])


def _coerce(data: dict, valid_domains: set[str], raw_text: str) -> Understanding:
    """Validate + normalise the LLM output into a trustworthy Understanding."""
    itype = str(data.get("type", "")).strip().lower()
    if itype not in ITEM_TYPES:
        itype = "idea"  # safest catch-all: keep it, don't force a fake task

    title = (str(data.get("title") or raw_text or "").strip())[:500] or raw_text.strip()

    domain = data.get("domain")
    domain = str(domain).strip().lower() if domain else None
    if domain in (None, "", "null", UNASSIGNED) or domain not in valid_domains:
        domain = None if domain in (None, "", "null") else (
            domain if domain in valid_domains else UNASSIGNED)
        if domain not in valid_domains:
            domain = UNASSIGNED

    size = data.get("size")
    size = str(size).strip().lower() if size else None
    if size not in SIZES:
        size = "medium" if itype == "task" else None

    def _clean(v):
        if v is None:
            return None
        v = str(v).strip()
        return v or None

    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    clarify = _clean(data.get("clarify"))
    # An actionable item that can't be placed, or low confidence, must ask (R2.5).
    if itype in {"task", "event"} and (domain == UNASSIGNED or confidence < CONFIDENCE_FLOOR):
        if not clarify:
            clarify = "أنا مش متأكد ده تحت أنهي مجال — تحب أحطه فين؟"

    return Understanding(
        type=itype,
        title=title,
        domain=domain,
        size=size,
        due=_clean(data.get("due")),
        trigger=_clean(data.get("trigger")),
        confidence=confidence,
        clarify=clarify,
        raw=raw_text,
    )


def interpret(text: str, domains: list[tuple[str, str]],
              client: LLMClient, names: list[str] | None = None) -> Understanding:
    """Interpret a capture. `domains` is [(name, label), …] from the live DB.

    On any failure (LLM down, unparseable reply) we DO NOT invent an answer — we
    return a low-confidence Understanding that asks the owner, and the caller keeps
    the capture for retry (R2.7).
    """
    valid = {name for name, _ in domains}
    text = (text or "").strip()
    if not text:
        return Understanding(type="idea", title="", domain=UNASSIGNED,
                             confidence=0.0, clarify="مفيش نص أفهمه — تبعت تاني؟", raw=text)
    try:
        reply = client.complete(_SYSTEM, _build_user_prompt(text, domains, names))
        data = _extract_json(reply)
    except Exception:
        # graceful: never crash, never guess. This is a SERVICE failure, so mark it
        # retryable — the caller keeps the capture 'unprocessed' and re-tries later.
        return Understanding(type="idea", title=text[:200], domain=UNASSIGNED,
                             confidence=0.0,
                             clarify="مش قادر أحلّلها دلوقتي، هعيد المحاولة — أو وضّحها لو تحب",
                             raw=text, retryable=True)
    return _coerce(data, valid, text)
