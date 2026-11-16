"""Bringing the Bonfire calendar in line with the predictions.

The horizon is the next 18 months (`horizon`), whatever the year; after Lewes
night this year keeps only known dates (see `predict.prediction_year`). Events dated before
today are never written or removed. Only successful writes are recorded, so a
failure is simply retried on the next sync.

Before planning, the calendar is read back (`reconcile`), so the record in
state.json is checked against what is really there: an event of ours deleted by
hand is restored, a duplicate removed, and one the record lost is adopted
rather than made again. Events without this tool's mark are never touched,
only listed.
"""
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from calendar import monthrange
from datetime import date
from pathlib import Path

from . import store
from .calendar_app import Calendar, CalendarError, Change, Found, payload
from .model import Catalogue
from .predict import Prediction, going_text, prediction_year, predictions


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
    action: str  # "add", "restore", "move", "update" or "remove"
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
    foreign: list[Found] = field(default_factory=list)  # events this tool didn't make: left alone
    read_error: str | None = None  # the calendar couldn't be read back; the record was trusted


@dataclass
class Repairs:
    """What reading the calendar back found, beyond the record."""
    restored: set[str] = field(default_factory=set)  # keys whose event was deleted by hand
    adopted: set[str] = field(default_factory=set)  # keys found in the calendar but not in the record
    duplicates: list[Found] = field(default_factory=list)
    foreign: list[Found] = field(default_factory=list)


def reconcile(state: store.State, live: list[Found], today: date) -> Repairs:
    """Bring the record (state, changed in place) in line with the events really there."""
    fixes = Repairs(foreign=sorted((f for f in live if f.key is None), key=lambda f: (f.day, f.title)))
    ours: dict[str, list[Found]] = {}
    for f in live:
        if f.key is not None:
            ours.setdefault(f.key, []).append(f)
    there = {f.uid for f in live}
    for k, e in list(state.events.items()):
        if date.fromisoformat(e["day"]) < today or e["uid"] in there:
            continue
        if k in ours:  # there under another ID: point the record at it and rewrite it
            state.events[k] = {"uid": ours[k][0].uid, "day": ours[k][0].day.isoformat(), "hash": ""}
            fixes.adopted.add(k)
        else:
            del state.events[k]
            fixes.restored.add(k)
    for k, found in ours.items():
        if k not in state.events:
            state.events[k] = {"uid": found[0].uid, "day": found[0].day.isoformat(), "hash": ""}
            fixes.adopted.add(k)
    recorded = {e["uid"] for e in state.events.values()}
    for k, found in ours.items():
        keep = state.events[k]["uid"]
        fixes.duplicates += [f for f in found if f.uid != keep and f.uid not in recorded]
    return fixes


HORIZON_MONTHS = 18


def horizon(today: date) -> date:
    """The first day past the calendar's reach: 18 months on (the month's last
    day when that month is shorter)."""
    months = today.month - 1 + HORIZON_MONTHS
    year, month = today.year + months // 12, months % 12 + 1
    return date(year, month, min(today.day, monthrange(year, month)[1]))


def wanted(cat: Catalogue, today: date) -> dict[str, Prediction]:
    """Everything from today up to the horizon; once this year's season is
    decided (after Lewes night), only this year's known dates."""
    decided = prediction_year(cat, today) > today.year
    end = horizon(today)
    found = [p for year in range(today.year, end.year + 1) for p in predictions(cat, year)
             if not (decided and year == today.year and not p.confirmed)]
    return {p.key: p for p in found if today <= p.day < end}


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
    hours = going_text(p.hours) if p.hours else None
    if before.get("hours") != hours and (hours or before.get("hours")):  # going marked, changed or taken off
        changes.append(f"now {hours}" if hours else "back to all-day" if p.all_day else "back to its own time")
    recorded = "percent" in before and "title" in before
    item.note = ", ".join(changes) or ("notes changed" if recorded else "title or notes changed")
    return item


def _removal_item(cat: Catalogue, key: str, before: dict) -> Item:
    sid = key.rsplit(":", 1)[0]
    title = before.get("title") or (f"{cat.societies[sid].name}" if sid in cat.societies else key)
    return Item("remove", key, date.fromisoformat(before["day"]), title)


def _record(p: Prediction, uid: str) -> dict:
    return {"uid": uid, "day": p.day.isoformat(), "hash": fingerprint(p), "title": p.title, "percent": p.percent,
            "hours": going_text(p.hours) if p.hours else None}


def run(cat: Catalogue, cal: Calendar, state_path: Path, today: date, dry_run: bool,
        on_start: Callable[[int], None] = lambda n: None) -> SyncResult:
    """on_start is told how many changes there are, just before they are written."""
    state = store.load(state_path)
    want = wanted(cat, today)
    try:
        fixes = reconcile(state, cal.read(today, date(horizon(today).year + 1, 1, 1)), today)
        read_error = None
    except CalendarError as e:
        fixes, read_error = Repairs(), str(e)
    todo = plan(cat, state, today)
    # Pair every change with its key, so no outcome is matched back by uid.
    pairs = [(p.key, Change(state.events.get(p.key, {}).get("uid"), p)) for p in todo.upserts]
    items = [_upsert_item(p, state.events.get(p.key)) for p in todo.upserts]
    for item in items:
        if item.key in fixes.restored:
            item.action, item.note = "restore", "was deleted from the calendar"
        elif item.key in fixes.adopted and item.action == "update":
            item.note = "not in the record"
    held = {state.events[k]["uid"] for k in want if k in state.events}
    stale: list[str] = []
    removing: set[str] = set()
    for f in fixes.duplicates:
        removing.add(f.uid)
        pairs.append((f.key, Change(f.uid)))
        items.append(Item("remove", f.key, f.day, f.title, note="duplicate"))
    for k in todo.removals:
        uid = state.events[k]["uid"]
        if uid in held or uid in removing:
            stale.append(k)  # a stale entry for an event that stays, or is already being removed
        else:
            removing.add(uid)
            pairs.append((k, Change(uid)))
            items.append(_removal_item(cat, k, state.events[k]))
            if k in fixes.adopted:
                items[-1].note = "not in the record"
    result = SyncResult(plan=todo, items=items, unchanged=len(want) - len(todo.upserts),
                        events=sorted(want.values(), key=lambda p: (p.day, p.title)),
                        foreign=fixes.foreign, read_error=read_error)
    if dry_run:
        result.written, result.removed = len(todo.upserts), len(todo.removals) + len(fixes.duplicates)
        return result
    if pairs:
        on_start(len(pairs))
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
    repaired = fixes.restored or fixes.adopted
    if changes or stale or filled or repaired:
        store.save(state, state_path, today)
    return result
