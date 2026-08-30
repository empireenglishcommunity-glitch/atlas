"""The Morning Brief (R4) — a decided plan, not a raw list.

Sections, in order: today's shape → the 3 that matter (deep-work first) → what's
being neglected → one decision. Detailed enough to be a 2-3 minute listen. Produces
two renderings: `.text` for Telegram (emoji, structure) and `.spoken` for Kokoro
(plain, no markup, natural sentences).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .allocator import DayPlan, Slotted
from .guardian import Neglect


@dataclass
class BriefText:
    text: str      # Telegram-facing (markdown-ish, emoji)
    spoken: str    # TTS-facing (plain prose)


_ENERGY_WORD = {5: "high", 4: "good", 3: "steady", 2: "low", 1: "very low"}


def _shape_line(free_hours: float, energy: Optional[int]) -> tuple[str, str]:
    hrs = f"~{free_hours:g}h of focus" if free_hours else "an open day"
    if energy:
        e = _ENERGY_WORD.get(energy, "steady")
        return (f"🗓️ Today: {hrs}, energy {e}.",
                f"Today you've got {hrs}, and your energy's been {e}.")
    return (f"🗓️ Today: {hrs}.", f"Today you've got {hrs}.")


def _slot_line(s: Slotted) -> str:
    return f"{s.item.title} — {s.slot}, ~{s.minutes}m"


def compose_brief(now: datetime, free_hours: float, plan: DayPlan,
                  neglects: list[Neglect], energy: Optional[int] = None,
                  decision: Optional[str] = None,
                  filed_since: int = 0) -> BriefText:
    """Assemble the brief from the day's plan + guardian flags + optional decision."""
    date_str = now.strftime("%A %d %b")
    shape_t, shape_s = _shape_line(free_hours, energy)

    # ── text (Telegram) ──
    T: list[str] = [f"*Atlas — {date_str}*", "", shape_t, ""]
    S: list[str] = [f"Morning. {shape_s}"]

    if plan.top:
        T.append("*The 3 that matter:*")
        S.append("Here are the three that matter.")
        for i, s in enumerate(plan.top, 1):
            T.append(f"{i}. {_slot_line(s)}")
            S.append(f"{i}: {s.item.title}, in the {s.slot}, about {s.minutes} minutes.")
        T.append("")
    else:
        T.append("_Nothing queued — a clear day. Want to set an intention?_")
        S.append("Nothing's queued today — it's a clear day.")

    if neglects:
        T.append("*Going quiet:*")
        S.append("Now, what's slipping.")
        for n in neglects[:3]:
            T.append(f"• {n.line()}")
            S.append(f"{n.label} has been quiet {n.silent_days} days — {n.suggested_action}")
        T.append("")

    # one decision — from an explicit prompt, or surfaced from over-capacity
    the_decision = decision or plan.tradeoff
    if the_decision:
        T.append(f"*One decision:* {the_decision}")
        S.append(f"One decision for you. {the_decision}")

    if filed_since:
        T.append("")
        T.append(f"_(I filed {filed_since} note{'s' if filed_since != 1 else ''} "
                 f"since yesterday — all sorted.)_")
        S.append(f"By the way, I filed {filed_since} of your notes since yesterday, all sorted.")

    return BriefText(text="\n".join(T).strip(), spoken=" ".join(S).strip())


def evening_prompt() -> str:
    """The 20-second close (R7): what happened + one feeling question."""
    return (
        "🌙 *Evening check-in*\n"
        "1) What did you actually get done today? (a line is enough)\n"
        "2) Energy today, 1–5?"
    )
