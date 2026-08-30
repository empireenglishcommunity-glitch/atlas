"""Durable plain-markdown mirror (R5.4/R9.4).

SQLite is the operating store; this is the archive that survives Atlas itself —
readable in any text editor, portable, greppable, and a hedge against DB loss. One
file per month under the archive dir. Never contains secrets; the dir is git-ignored.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path


def append(archive_dir: str, kind: str, text: str, now: datetime,
           domain: str | None = None) -> None:
    """Append one dated line to the current month's markdown file. Never raises
    (an archive failure must never break the live flow)."""
    try:
        Path(archive_dir).mkdir(parents=True, exist_ok=True)
        month_file = Path(archive_dir) / f"{now.strftime('%Y-%m')}.md"
        stamp = now.strftime("%Y-%m-%d %H:%M")
        where = f" _(#{domain})_" if domain else ""
        line = f"- `{stamp}` **{kind}**{where}: {text}\n"
        if not month_file.exists():
            month_file.write_text(f"# Atlas archive — {now.strftime('%B %Y')}\n\n", encoding="utf-8")
        with month_file.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass  # archive is best-effort; the SQLite record is the source of truth
