"""Bringing the Bonfire calendar in line with the predictions.

The horizon is the rest of this year and all of next. Events dated before
today are never written or removed. Only successful writes are recorded, so a
failure is simply retried on the next sync.
"""
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import store
from .calendar_app import Calendar, CalendarError, Change, payload
from .model import Catalogue
from .predict import Prediction, predictions


def fingerprint(p: Prediction) -> str:
    body = {k: v for k, v in payload(Change(None, p)).items() if k != "uid"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


@dataclass
class SyncPlan:
    upserts: list[Prediction] = field(default_factory=list)
    removals: list[str] = field(default_factory=list)


@dataclass
class SyncResult:
    written: int = 0
    removed: int = 0
    failed: list[tuple[str, str]] = field(default_factory=list)
    plan: SyncPlan = field(default_factory=SyncPlan)


def wanted(cat: Catalogue, today: date) -> dict[str, Prediction]:
    found = [p for year in (today.year, today.year + 1) for p in predictions(cat, year)]
    return {p.key: p for p in found if p.day >= today}


def plan(cat: Catalogue, state: store.State, today: date) -> SyncPlan:
    want = wanted(cat, today)
    upserts = [p for k, p in want.items() if state.events.get(k, {}).get("hash") != fingerprint(p)]
    removals = [k for k, e in state.events.items()
                if k not in want and date.fromisoformat(e["day"]) >= today]
    return SyncPlan(upserts, removals)


def run(cat: Catalogue, cal: Calendar, state_path: Path, today: date, dry_run: bool) -> SyncResult:
    state = store.load(state_path)
    todo = plan(cat, state, today)
    if dry_run:
        return SyncResult(len(todo.upserts), len(todo.removals), [], todo)
    # Pair every change with its key, so no outcome is matched back by uid.
    pairs = [(p.key, Change(state.events.get(p.key, {}).get("uid"), p)) for p in todo.upserts]
    held = {state.events[k]["uid"] for k in wanted(cat, today) if k in state.events}
    dropped = False
    removing: set[str] = set()
    for k in todo.removals:
        uid = state.events[k]["uid"]
        if uid in held or uid in removing:
            del state.events[k]  # a stale entry for an event that stays, or is already being removed
            dropped = True
        else:
            removing.add(uid)
            pairs.append((k, Change(uid)))
    result = SyncResult(plan=todo)
    changes = [c for _, c in pairs]
    for (key, change), outcome in zip(pairs, cal.apply(changes), strict=True):
        if isinstance(outcome, CalendarError):
            result.failed.append((key, str(outcome)))
        elif change.prediction:
            p = change.prediction
            state.events[key] = {"uid": outcome, "day": p.day.isoformat(), "hash": fingerprint(p)}
            result.written += 1
        else:
            for k in [k for k, e in state.events.items() if e["uid"] == change.uid and k in todo.removals]:
                del state.events[k]
            result.removed += 1
    if changes or dropped:
        store.save(state, state_path, today)
    return result
