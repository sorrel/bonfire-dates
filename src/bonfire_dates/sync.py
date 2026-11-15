"""Bringing the Bonfire calendar in line with the predictions.

The horizon is the rest of this year and all of next; after Lewes night this
year keeps only known dates (see `predict.prediction_year`). Events dated before
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
from .predict import Prediction, prediction_year, predictions


def fingerprint(p: Prediction) -> str:
    body = {k: v for k, v in payload(Change(None, p)).items() if k != "uid"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


@dataclass
class SyncPlan:
    upserts: list[Prediction] = field(default_factory=list)
    removals: list[str] = field(default_factory=list)


@dataclass
class Item:
    """One change a sync makes (or, in a dry run, would make), for the report."""
    action: str  # "add", "move", "update" or "remove"
    key: str
    day: date
    title: str
    percent: int | None = None
    confirmed: bool = False
    note: str = ""  # what changed: "was Sat 23 Oct", "was 56%"
    error: str | None = None


@dataclass
class SyncResult:
    written: int = 0
    removed: int = 0
    failed: list[tuple[str, str]] = field(default_factory=list)
    plan: SyncPlan = field(default_factory=SyncPlan)
    items: list[Item] = field(default_factory=list)
    unchanged: int = 0
    events: list[Prediction] = field(default_factory=list)  # every event the calendar should now hold


def wanted(cat: Catalogue, today: date) -> dict[str, Prediction]:
    """Everything still to come this year and next; once this year's season is
    decided (after Lewes night), only this year's known dates."""
    decided = prediction_year(cat, today) > today.year
    found = [p for year in (today.year, today.year + 1) for p in predictions(cat, year)
             if not (decided and year == today.year and not p.confirmed)]
    return {p.key: p for p in found if p.day >= today}


def plan(cat: Catalogue, state: store.State, today: date) -> SyncPlan:
    want = wanted(cat, today)
    upserts = [p for k, p in want.items() if state.events.get(k, {}).get("hash") != fingerprint(p)]
    removals = [k for k, e in state.events.items()
                if k not in want and date.fromisoformat(e["day"]) >= today]
    return SyncPlan(upserts, removals)


def _upsert_item(p: Prediction, before: dict | None) -> Item:
    item = Item("add", p.key, p.day, p.title, p.percent, p.confirmed)
    if before is None:
        return item
    old_day = date.fromisoformat(before["day"])
    if old_day != p.day:
        item.action, item.note = "move", f"was {old_day:%a %d %b}" + (
            f" {old_day.year}" if old_day.year != p.day.year else "")
        return item
    item.action = "update"
    changes = []
    if before.get("percent") is not None and before["percent"] != p.percent:
        changes.append(f"was {before['percent']}%")
    if before.get("title") and before["title"].rstrip("?") != p.title.rstrip("?"):  # older titles ended in "?" below 70%
        changes.append(f"was “{before['title']}”")
    recorded = "percent" in before and "title" in before
    item.note = ", ".join(changes) or ("notes changed" if recorded else "title or notes changed")
    return item


def _removal_item(cat: Catalogue, key: str, before: dict) -> Item:
    sid = key.rsplit(":", 1)[0]
    title = before.get("title") or (f"{cat.societies[sid].name}" if sid in cat.societies else key)
    return Item("remove", key, date.fromisoformat(before["day"]), title)


def _record(p: Prediction, uid: str) -> dict:
    return {"uid": uid, "day": p.day.isoformat(), "hash": fingerprint(p), "title": p.title, "percent": p.percent}


def run(cat: Catalogue, cal: Calendar, state_path: Path, today: date, dry_run: bool) -> SyncResult:
    state = store.load(state_path)
    want = wanted(cat, today)
    todo = plan(cat, state, today)
    # Pair every change with its key, so no outcome is matched back by uid.
    pairs = [(p.key, Change(state.events.get(p.key, {}).get("uid"), p)) for p in todo.upserts]
    items = [_upsert_item(p, state.events.get(p.key)) for p in todo.upserts]
    held = {state.events[k]["uid"] for k in want if k in state.events}
    stale: list[str] = []
    removing: set[str] = set()
    for k in todo.removals:
        uid = state.events[k]["uid"]
        if uid in held or uid in removing:
            stale.append(k)  # a stale entry for an event that stays, or is already being removed
        else:
            removing.add(uid)
            pairs.append((k, Change(uid)))
            items.append(_removal_item(cat, k, state.events[k]))
    result = SyncResult(plan=todo, items=items, unchanged=len(want) - len(todo.upserts),
                        events=sorted(want.values(), key=lambda p: (p.day, p.title)))
    if dry_run:
        result.written, result.removed = len(todo.upserts), len(todo.removals)
        return result
    for k in stale:
        del state.events[k]
    # Older state lacks titles and percentages; fill them in for events that stay as they are.
    filled = False
    for k, p in want.items():
        e = state.events.get(k)
        if e and e.get("hash") == fingerprint(p) and "percent" not in e:
            state.events[k] = _record(p, e["uid"])
            filled = True
    changes = [c for _, c in pairs]
    for (key, change), outcome, item in zip(pairs, cal.apply(changes), items, strict=True):
        if isinstance(outcome, CalendarError):
            result.failed.append((key, str(outcome)))
            item.error = str(outcome)
        elif change.prediction:
            state.events[key] = _record(change.prediction, outcome)
            result.written += 1
        else:
            for k in [k for k, e in state.events.items() if e["uid"] == change.uid and k in todo.removals]:
                del state.events[k]
            result.removed += 1
    if changes or stale or filled:
        store.save(state, state_path, today)
    return result
