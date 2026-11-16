"""The shapes everything else shares: societies, their rules and their evidence."""
from dataclasses import dataclass, field
from datetime import date, time

# Trust order, highest first. A source says how a date is known, never by whom.
SOURCES = ("verified", "society", "guides", "guide", "wiki")
# visiting: a society with no home location, procession or event of its own.
KINDS = ("night", "badge", "other", "visiting")
STATUSES = ("active", "unknown", "gone")
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DIRECTIONS = ("before", "after", "nearest")
FIXED_ANCHORS = ("nov5", "remembrance-sunday")


@dataclass(frozen=True)
class Evidence:
    source: str
    url: str | None = None
    checked: date | None = None
    note: str | None = None


@dataclass(frozen=True)
class Known:
    date: date
    evidence: Evidence


@dataclass(frozen=True)
class Rule:
    """One of three forms: nth weekday of a month; a fixed day of a month
    (optionally moved off a Sunday); or relative to an anchor."""
    month: int | None = None
    day: int | None = None
    nth: int | None = None
    weekday: str | None = None
    anchor: str | None = None
    direction: str | None = None
    weeks: int = 0
    days: int = 0
    sunday: str | None = None
    guess: bool = False
    evidence: Evidence | None = None


@dataclass(frozen=True)
class Society:
    id: str
    name: str
    kind: str
    status: str
    place: str | None = None
    start: time | None = None
    rule: Rule | None = None
    known: tuple[Known, ...] = ()
    of: str | None = None
    links: dict[str, str] = field(default_factory=dict)
    emoji: str | None = None
    confidence: int | None = None
    why: str | None = None
    rate_on_evidence: bool = False
    note: str | None = None
    searched: date | None = None  # the last day new sources were looked for

    def known_in(self, year: int) -> Known | None:
        """The year's known date: the best-trusted one, and the latest recorded among
        equals (confirmed.toml loads after the seed data, so a correction wins)."""
        found = [k for k in self.known if k.date.year == year]
        return min(reversed(found), key=lambda k: SOURCES.index(k.evidence.source), default=None)


@dataclass(frozen=True)
class Catalogue:
    societies: dict[str, Society]
    badge_confidence: int = 10
