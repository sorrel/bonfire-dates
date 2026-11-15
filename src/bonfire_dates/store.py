"""Local state in data/state.json: which calendar event holds which prediction.

Each entry is keyed by event key ("firle:2027") and holds the event's uid, its
day and a hash of what was written, so an unchanged event isn't rewritten.
"""
import json
import os
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

KEEP_BACKUPS = 30


@dataclass
class State:
    events: dict[str, dict]


def load(path: Path) -> State:
    if not path.exists():
        return State({})
    return State(json.loads(path.read_text()).get("events", {}))


def backup(path: Path, today: date) -> None:
    """Before the day's first save, keep the state as it was. The last 30 are kept."""
    if not path.exists():
        return
    folder = path.parent / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"state-{today.isoformat()}.json"
    if not target.exists():
        shutil.copy2(path, target)
    for old in sorted(folder.glob("state-????-??-??.json"))[:-KEEP_BACKUPS]:
        old.unlink()


def save(state: State, path: Path, today: date) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup(path, today)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"events": state.events}, indent=1, sort_keys=True, ensure_ascii=False))
    os.replace(tmp, path)
