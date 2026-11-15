"""Recording what research finds: confirmed dates, local evidence, and what's left to look for."""
import difflib
import json
import shutil
from datetime import date
from pathlib import Path

import click

from .model import Catalogue, Society
from .predict import Prediction, predictions


def _toml_string(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)  # a JSON string is a valid TOML basic string


def append_confirmed(path: Path, society_id: str, day: date, source: str, url: str | None,
                     checked: date) -> None:
    """Add one [[confirmed]] entry to the end of confirmed.toml, as text (no TOML writer needed)."""
    lines = ["", "[[confirmed]]", f"society = {_toml_string(society_id)}", f"date = {day.isoformat()}",
             f"source = {_toml_string(source)}"]
    if url:
        lines.append(f"url = {_toml_string(url)}")
    lines.append(f"checked = {checked.isoformat()}")
    with path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def evidence_dir(data_dir: Path, society_id: str) -> Path:
    return data_dir / "evidence" / society_id


def file_evidence(data_dir: Path, society_id: str, src: Path, today: date) -> Path:
    """Copy a poster, screenshot or saved page in as evidence/<id>/<date>-<name>, never overwriting."""
    folder = evidence_dir(data_dir, society_id)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{today.isoformat()}-{src.name}"
    n = 2
    while target.exists():
        target = folder / f"{today.isoformat()}-{src.stem}-{n}{src.suffix}"
        n += 1
    shutil.copy2(src, target)
    return target


def resolve_id(cat: Catalogue, text: str) -> str:
    if text in cat.societies:
        return text
    near = difflib.get_close_matches(text, cat.societies, n=3, cutoff=0.5)
    hint = f" Did you mean {', '.join(near)}?" if near else " `bonfire list` shows them all."
    raise click.BadParameter(f"no society {text!r}.{hint}", param_hint="SOCIETY")


def last_checked(s: Society) -> date | None:
    """The most recent day any of the society's evidence was checked."""
    days = [k.evidence.checked for k in s.known if k.evidence.checked]
    if s.rule and s.rule.evidence and s.rule.evidence.checked:
        days.append(s.rule.evidence.checked)
    return max(days, default=None)


def todo(cat: Catalogue, year: int, today: date) -> list[Prediction]:
    """The year's events still only predicted, from today on, soonest first."""
    return [p for p in predictions(cat, year) if not p.confirmed and p.day >= today]
