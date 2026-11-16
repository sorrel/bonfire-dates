"""Reading societies.toml (and confirmed.toml) into a Catalogue.

Every problem is collected before anything is raised, so one run of
`bonfire check` lists them all, each naming its file and society. Values are
type- and range-checked here so that nothing downstream can crash on them.
"""
import calendar
import tomllib
from dataclasses import replace
from datetime import date, time
from pathlib import Path

from .model import (DIRECTIONS, FIXED_ANCHORS, KINDS, SOURCES, STATUSES, WEEKDAYS, Catalogue, Evidence,
                    Known, Rule, Society)

SOCIETY_KEYS = {"name", "kind", "status", "place", "start", "rule", "known", "of", "links", "emoji",
                "confidence", "why", "rate_on_evidence", "note", "searched"}
RULE_KEYS = {"month", "day", "nth", "weekday", "anchor", "direction", "weeks", "days", "sunday", "guess",
             "source", "url", "checked", "note"}
EVIDENCE_KEYS = {"date", "source", "url", "checked", "note"}
LINK_KEYS = {"website", "facebook", "x", "instagram"}
TEXT_KEYS = ("name", "place", "of", "emoji", "why", "note")


class DataError(Exception):
    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("\n".join(problems))


def _read(path: Path) -> dict:
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise DataError([f"{path.name}: {e}"]) from None  # the message gives line and column
    except UnicodeDecodeError:
        raise DataError([f"{path.name}: not valid UTF-8 text"]) from None
    except OSError as e:
        raise DataError([f"{path.name}: can't be read ({e.strerror})"]) from None


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _text(raw: dict, key: str, where: str, out: list[str]) -> str | None:
    v = raw.get(key)
    if v is not None and not isinstance(v, str):
        out.append(f"{where}: {key} must be text")
        return None
    return v


def _evidence(raw: dict, where: str, out: list[str]) -> Evidence:
    source = raw.get("source")
    if source not in SOURCES:
        out.append(f"{where}: unknown source {source!r} (use one of {', '.join(SOURCES)})")
    checked = raw.get("checked")
    if checked is not None and not isinstance(checked, date):
        out.append(f"{where}: checked must be a date")
        checked = None
    return Evidence(str(source), _text(raw, "url", where, out), checked, _text(raw, "note", where, out))


def _rule(raw, where: str, out: list[str]) -> Rule | None:
    if not isinstance(raw, dict):
        out.append(f"{where}: rule must be a table, like {{ month = 9, weekday = \"sat\", nth = 1 }}")
        return None
    bad = len(out)
    for k in raw.keys() - RULE_KEYS:
        out.append(f"{where}: unknown rule key {k!r}")
    for k in ("month", "day", "nth", "weeks", "days"):
        if k in raw and not _is_int(raw[k]):
            out.append(f"{where}: {k} must be a whole number")
    month, day, nth = raw.get("month"), raw.get("day"), raw.get("nth")
    if _is_int(month) and not 1 <= month <= 12:
        out.append(f"{where}: month must be 1 to 12")
    if _is_int(nth) and nth not in (1, 2, 3, 4, 5, -1):
        out.append(f"{where}: nth must be 1 to 5, or -1 for the last")
    if _is_int(day) and _is_int(month) and 1 <= month <= 12 and not 1 <= day <= calendar.monthrange(2028, month)[1]:
        out.append(f"{where}: day {day} doesn't exist in month {month}")
    if raw.get("weekday") is not None and raw["weekday"] not in WEEKDAYS:
        out.append(f"{where}: unknown weekday {raw['weekday']!r}")
    if raw.get("direction") is not None and raw["direction"] not in DIRECTIONS:
        out.append(f"{where}: unknown direction {raw['direction']!r}")
    if raw.get("anchor") is not None and not isinstance(raw["anchor"], str):
        out.append(f"{where}: anchor must be text")
    if raw.get("sunday") not in (None, "sat-before"):
        out.append(f"{where}: sunday must be \"sat-before\"")
    forms = [raw.get("anchor") is not None, nth is not None, day is not None]
    if sum(forms) != 1:
        out.append(f"{where}: a rule needs exactly one of anchor, nth (with month) or day (with month)")
    if (forms[1] or forms[2]) and month is None:
        out.append(f"{where}: a nth or day rule needs a month")
    if forms[1] and not raw.get("weekday"):
        out.append(f"{where}: a nth rule needs a weekday")
    ev = _evidence(raw, where, out) if "source" in raw else None
    if len(out) > bad:
        return None
    return Rule(month, day, nth, raw.get("weekday"), raw.get("anchor"), raw.get("direction"),
                raw.get("weeks", 0), raw.get("days", 0), raw.get("sunday"), bool(raw.get("guess", False)), ev)


def _start(raw, where: str, out: list[str]) -> time | None:
    if raw is None:
        return None
    try:
        return time.fromisoformat(raw)
    except (TypeError, ValueError):
        out.append(f"{where}: start must be a time like \"18:30\"")
        return None


def _known(raw, where: str, out: list[str]) -> Known | None:
    if not isinstance(raw, dict):
        out.append(f"{where}: each known date must be a table, like {{ date = 2026-10-24, source = \"verified\" }}")
        return None
    for k in raw.keys() - EVIDENCE_KEYS - {"society"}:
        out.append(f"{where}: unknown key {k!r}")
    d = raw.get("date")
    if not isinstance(d, date):
        out.append(f"{where}: date must be a date like 2027-10-23")
        return None
    return Known(d, _evidence(raw, where, out))


def _society(sid: str, raw, fname: str, out: list[str]) -> Society | None:
    where = f"{fname}: [{sid}]"
    if not isinstance(raw, dict):
        out.append(f"{where}: must be a table (a [{sid}] section), not a single value")
        return None
    for k in raw.keys() - SOCIETY_KEYS:
        out.append(f"{where}: unknown key {k!r}")
    texts = {k: _text(raw, k, where, out) for k in TEXT_KEYS}
    if not texts["name"]:
        out.append(f"{where}: name is missing")
    if raw.get("kind") not in KINDS:
        out.append(f"{where}: kind must be one of {', '.join(KINDS)}")
    if raw.get("status") not in STATUSES:
        out.append(f"{where}: status must be one of {', '.join(STATUSES)}")
    links = raw.get("links", {})
    if not isinstance(links, dict) or not all(isinstance(v, str) for v in links.values()):
        out.append(f"{where}: links must be a table of addresses, like {{ website = \"https://…\" }}")
        links = {}
    for k in links.keys() - LINK_KEYS:
        out.append(f"{where}: unknown link {k!r}")
    rule = _rule(raw["rule"], f"{where} rule", out) if "rule" in raw else None
    known_raw = raw.get("known", [])
    if not isinstance(known_raw, list):
        out.append(f"{where}: known must be a list of dates")
        known_raw = []
    known = tuple(k for i, r in enumerate(known_raw) if (k := _known(r, f"{where} known #{i + 1}", out)))
    conf = raw.get("confidence")
    if conf is not None and not (_is_int(conf) and 1 <= conf <= 100):
        out.append(f"{where}: confidence must be a whole number from 1 to 100")
        conf = None
    searched = raw.get("searched")
    if searched is not None and not isinstance(searched, date):
        out.append(f"{where}: searched must be a date, like 2026-11-16")
        searched = None
    return Society(sid, texts["name"] or sid, raw.get("kind", "night"), raw.get("status", "active"),
                   texts["place"], _start(raw.get("start"), where, out), rule, known, texts["of"],
                   dict(links), texts["emoji"], conf, texts["why"], bool(raw.get("rate_on_evidence", False)),
                   texts["note"], searched)


def problems(cat: Catalogue, fname: str = "societies.toml") -> list[str]:
    """Checks that need the whole catalogue: anchors and `of` that name nothing, and anchor cycles."""
    out: list[str] = []
    ids = cat.societies
    for s in ids.values():
        a = s.rule.anchor if s.rule else None
        if a and a not in FIXED_ANCHORS and a not in ids:
            out.append(f"{fname}: [{s.id}] anchor {a!r} is not a society or a fixed anchor")
        if s.of and s.of not in ids:
            out.append(f"{fname}: [{s.id}] of {s.of!r} is not a society")
    seen: set[str] = set()
    for start in ids:
        path: list[str] = []
        sid = start
        while sid in ids and sid not in seen:
            if sid in path:
                loop = path[path.index(sid):]
                out.append(f"{fname}: anchor cycle: {' → '.join([*loop, sid])}")
                break
            path.append(sid)
            rule = ids[sid].rule
            sid = rule.anchor if rule and rule.anchor else ""
        seen.update(path)
    return out


def load(societies_path: Path, confirmed_path: Path | None, local_path: Path | None = None) -> Catalogue:
    """The public societies file, plus dates from confirmed.toml (public) and, if
    given, a private file of dates known first-hand (gitignored data/known.toml)."""
    raw = _read(societies_path)
    out: list[str] = []
    defaults = raw.pop("defaults", {})
    badge = defaults.get("badge_confidence", 10) if isinstance(defaults, dict) else None
    if not (_is_int(badge) and 1 <= badge <= 100):
        out.append(f"{societies_path.name}: [defaults] badge_confidence must be a whole number from 1 to 100")
        badge = 10
    societies = {sid: s for sid, body in raw.items() if (s := _society(sid, body, societies_path.name, out))}
    for extra in (confirmed_path, local_path):
        if extra is None or not extra.exists():
            continue
        entries = _read(extra).get("confirmed", [])
        for i, entry in enumerate(entries if isinstance(entries, list) else []):
            where = f"{extra.name}: entry #{i + 1}"
            sid = entry.get("society") if isinstance(entry, dict) else None
            if sid not in societies:
                out.append(f"{where}: unknown society {sid!r}")
                continue
            if k := _known(entry, where, out):
                s = societies[sid]
                societies[sid] = replace(s, known=(*s.known, k))
    cat = Catalogue(societies, badge)
    out += problems(cat, societies_path.name)
    if out:
        raise DataError(out)
    return cat
