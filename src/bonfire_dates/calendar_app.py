"""Putting predictions into the "Bonfire" calendar (synced to the phone through iCloud).

Adapted from albion-tickets. MacCalendar runs calendar.js (EventKit, through
osascript) once per batch of changes, passing them as JSON on stdin. The
script reports each change on its own line as soon as it is done, so a batch
cut short still says what it finished. FakeCalendar is the in-memory stand-in
every test uses.
"""
import json
import os
import selectors
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .predict import Prediction

SCRIPT = Path(__file__).with_name("calendar.js")
BASE_TIMEOUT_S = 150  # covers macOS's one-off "allow calendar access?" prompt
PER_CHANGE_S = 10


class CalendarError(Exception):
    pass


@dataclass(frozen=True)
class Change:
    """One calendar change: an upsert (prediction set) or a removal (prediction None)."""
    uid: str | None
    prediction: Prediction | None = None


class Calendar(Protocol):
    def apply(self, changes: list[Change]) -> list[str | CalendarError]: ...
    def check_ready(self) -> str | None: ...


class FakeCalendar:
    def __init__(self) -> None:
        self.events: dict[str, Prediction] = {}
        self.calls: list[tuple[str, str]] = []
        self.fail_keys: set[str] = set()  # keys whose writes fail, for tests
        self.ready: str | None = None

    def apply(self, changes: list[Change]) -> list[str | CalendarError]:
        out: list[str | CalendarError] = []
        for c in changes:
            if c.prediction is None:
                self.calls.append(("remove", c.uid))
                self.events.pop(c.uid, None)
                out.append(c.uid)
                continue
            if c.prediction.key in self.fail_keys:
                out.append(CalendarError("save failed"))
                continue
            # As calendar.js: the given ID, else an event already carrying this key, else a new one.
            same_key = next((u for u, p in self.events.items() if p.key == c.prediction.key), None)
            uid = c.uid if c.uid in self.events else same_key or uuid.uuid4().hex
            self.events[uid] = c.prediction
            self.calls.append(("upsert", c.prediction.key))
            out.append(uid)
        return out

    def check_ready(self) -> str | None:
        return self.ready


def payload(c: Change) -> dict:
    if c.prediction is None:
        return {"op": "remove", "uid": c.uid}
    p = c.prediction
    # An all-day event is sent with its end equal to its start: EventKit then makes
    # it exactly that one day (a next-midnight end can show across two days).
    # All-day events are floating, read in the Mac's own time zone: right while
    # the Mac is on UK time.
    end = p.start if p.all_day else p.end
    return {
        "op": "upsert", "uid": c.uid, "key": p.key, "title": p.title, "notes": p.notes,
        "start": int(p.start.timestamp() * 1000), "end": int(end.timestamp() * 1000),
        "allDay": p.all_day, "alarms": [], "location": p.society.place, "geo": None,
    }


class MacCalendar:
    def __init__(self, name: str, command: list[str] | None = None) -> None:
        self.name = name
        self.command = command or ["osascript", "-l", "JavaScript", str(SCRIPT)]  # tests swap in a stand-in

    def _run(self, ops: list[dict]) -> list[dict]:
        """Results line by line; stops at the deadline with what has arrived."""
        limit = BASE_TIMEOUT_S + PER_CHANGE_S * len(ops)
        deadline = time.monotonic() + limit
        proc = subprocess.Popen(self.command, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        proc.stdin.write(json.dumps({"calendar": self.name, "ops": ops}).encode())
        proc.stdin.close()
        results: list[dict] = []
        buf = b""
        sel = selectors.DefaultSelector()
        sel.register(proc.stdout, selectors.EVENT_READ)
        try:
            while len(results) < len(ops):
                left = deadline - time.monotonic()
                if left <= 0 or not sel.select(timeout=left):
                    break
                chunk = os.read(proc.stdout.fileno(), 65536)
                if not chunk:
                    break
                buf += chunk
                *lines, buf = buf.split(b"\n")
                results.extend(json.loads(line) for line in lines if line.strip())
        finally:
            sel.close()
            if proc.poll() is None:
                proc.kill()
            proc.wait()
        if len(results) < len(ops):
            why = proc.stderr.read().decode().strip() if proc.returncode not in (0, -9) else ""
            stop = why or f"the calendar did not finish within {limit} s"
            results.extend({"ok": False, "error": stop} for _ in range(len(ops) - len(results)))
        proc.stderr.close()
        proc.stdout.close()
        return results

    def apply(self, changes: list[Change]) -> list[str | CalendarError]:
        if not changes:
            return []
        out: list[str | CalendarError] = []
        for r in self._run([payload(c) for c in changes]):
            if r.get("ok") and (r.get("uid") or "") != "":
                out.append(r["uid"])
            else:
                out.append(CalendarError(r.get("error") or "no event ID came back"))
        return out

    def check_ready(self) -> str | None:
        result = self._run([{"op": "check"}])[0]
        if result.get("ok"):
            return None
        if result.get("error") == "missing":
            return f'Calendar "{self.name}" not found: create it in Calendar.app under your iCloud account'
        return f"Calendar not reachable: {result.get('error')}"
