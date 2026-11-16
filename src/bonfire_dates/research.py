"""Recording what research finds: confirmed dates, local evidence, and what's left to look for."""
import difflib
import json
import shutil
from datetime import date, time
from pathlib import Path

import click

from .model import Catalogue, Society
from .predict import Prediction, predictions
from .rules import rule_date


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


GOING_HEADER = "# Events you're going to, with your hours. Private: data/ is never committed.\n"


def write_going(path: Path, marks: dict[str, tuple[time, time]]) -> None:
    """Rewrite data/going.toml from the marks, soonest year first."""
    def order(key: str) -> tuple[int, str]:
        sid, _, year = key.rpartition(":")
        return int(year), sid

    lines = [GOING_HEADER]
    for key in sorted(marks, key=order):
        sid, _, year = key.rpartition(":")
        begin, finish = marks[key]
        lines += ["[[going]]", f"society = {_toml_string(sid)}", f"year = {year}",
                  f'from = "{begin:%H:%M}"', f'to = "{finish:%H:%M}"', ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".toml.tmp")
    tmp.write_text("\n".join(lines), encoding="utf-8")
    tmp.replace(path)


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
    """The most recent day any of the society's evidence was checked, or its sources searched for."""
    days = [k.evidence.checked for k in s.known if k.evidence.checked]
    if s.searched:
        days.append(s.searched)
    if s.rule and s.rule.evidence and s.rule.evidence.checked:
        days.append(s.rule.evidence.checked)
    return max(days, default=None)


def todo(cat: Catalogue, year: int, today: date) -> list[Prediction]:
    """The year's events still only predicted, from today on, soonest first."""
    return [p for p in predictions(cat, year) if not p.confirmed and p.day >= today]


FIFTH_LEEWAY = 3  # days: a rule this close to 5 November celebrates on or near it


def fifth_suspect(cat: Catalogue, society_id: str, day: date) -> date | None:
    """The society's rule date, when `day` is 5 November and the rule puts its
    night well away from it. Councils, schools and venues hold fireworks on the
    5th in towns whose society celebrates on another night, and listings mix
    them up. None when the date is not suspect (or the society has no rule)."""
    if (day.month, day.day) != (11, 5):
        return None
    ruled = rule_date(cat, society_id, day.year)
    if ruled is None or abs((ruled - day).days) <= FIFTH_LEEWAY:
        return None
    return ruled
