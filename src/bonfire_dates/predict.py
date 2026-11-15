"""A season's predicted events, each ready to become a calendar event."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from . import config
from .confidence import Rating, rate
from .model import Catalogue, Known, Society
from .rules import date_for, describe

EMOJI = {"night": "🔥", "badge": "🦡", "other": "🔥"}
EVENT_LENGTH = timedelta(hours=3)


def _evidence_line(k: Known) -> str:
    e = k.evidence
    bits = [f"{k.date:%a %d %b %Y} ({e.source}"]
    if e.checked:
        bits.append(f", checked {e.checked:%d %b %Y}")
    line = "".join(bits) + ")"
    if e.note:
        line += f": {e.note}"
    if e.url:
        line += f"\n  {e.url}"
    return line


@dataclass(frozen=True)
class Prediction:
    key: str
    society: Society
    day: date
    percent: int
    confirmed: bool
    rating: Rating
    rule_text: str

    @property
    def all_day(self) -> bool:
        return self.society.start is None

    @property
    def start(self) -> datetime:
        return datetime.combine(self.day, self.society.start or time(0), tzinfo=config.TZ)

    @property
    def end(self) -> datetime:
        if self.all_day:
            return datetime.combine(self.day + timedelta(days=1), time(0), tzinfo=config.TZ)
        return self.start + EVENT_LENGTH

    @property
    def title(self) -> str:
        emoji = self.society.emoji or EMOJI[self.society.kind]
        unsure = "?" if self.percent < config.QUESTION_BELOW else ""
        return f"{emoji} {self.society.name}{unsure}"

    @property
    def notes(self) -> str:
        lines = [f"Confidence {self.percent}%"]
        if self.confirmed:
            lines += ["Confirmed:", *(_evidence_line(k) for k in self.rating.matches)]
        else:
            lines.append(f"Rule: {self.rule_text} ({self.rating.why})")
            if self.rating.matches:
                lines += ["Fits:", *(_evidence_line(k) for k in self.rating.matches)]
            if self.rating.contradictions:
                lines += ["Misses:", *(_evidence_line(k) for k in self.rating.contradictions)]
        if self.society.note:
            lines.append(self.society.note)
        if not self.confirmed:
            lines.append("Predicted, not published.")
        return "\n".join(lines)


def predict_one(cat: Catalogue, society_id: str, year: int) -> Prediction | None:
    s = cat.societies[society_id]
    day = date_for(cat, society_id, year)
    if s.status != "active" or day is None:
        return None
    r = rate(cat, society_id, year)
    return Prediction(f"{s.id}:{year}", s, day, r.percent, r.confirmed, r, describe(cat, s.rule))


def predictions(cat: Catalogue, year: int) -> list[Prediction]:
    found = (predict_one(cat, sid, year) for sid in cat.societies)
    return sorted((p for p in found if p), key=lambda p: (p.day, p.society.name))


def prediction_year(cat: Catalogue, today: date) -> int:
    """The season being predicted: this year until Lewes night (5 November, or
    the Saturday before), next year after it. By then the rest of the season's
    dates are known, so the current year keeps only those."""
    lewes = date_for(cat, "lewes", today.year) if "lewes" in cat.societies else None
    return today.year if today <= (lewes or date(today.year, 11, 5)) else today.year + 1
