"""Turning a society's rule into a date for a given year, and into words."""
import calendar
from datetime import date, timedelta

from .model import WEEKDAYS, Catalogue, Rule

WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
ORDINALS = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th", -1: "last"}


def _nth_weekday(year: int, month: int, weekday: int, nth: int) -> date:
    if nth > 0:
        first = date(year, month, 1)
        return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (nth - 1))
    last = date(year, month, calendar.monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - weekday) % 7 + 7 * (-nth - 1))


def _before(d: date, weekday: int) -> date:
    return d - timedelta(days=(d.weekday() - weekday) % 7 or 7)


def _after(d: date, weekday: int) -> date:
    return d + timedelta(days=(weekday - d.weekday()) % 7 or 7)


def _anchor(cat: Catalogue, anchor: str, year: int) -> date | None:
    if anchor == "nov5":
        return date(year, 11, 5)
    if anchor == "remembrance-sunday":
        return _nth_weekday(year, 11, 6, 2)
    return date_for(cat, anchor, year)


def rule_date(cat: Catalogue, society_id: str, year: int) -> date | None:
    """The rule's date for the year, ignoring the society's own known dates.
    An anchor society's known date does count: if Newick moves, Firle follows."""
    rule = cat.societies[society_id].rule
    if rule is None:
        return None
    wd = WEEKDAYS.index(rule.weekday) if rule.weekday else None
    if rule.nth is not None:
        d = _nth_weekday(year, rule.month, wd, rule.nth)
    elif rule.day is not None:
        if rule.day > calendar.monthrange(year, rule.month)[1]:
            return None  # 29 February, in a year without one
        d = date(year, rule.month, rule.day)
        if rule.sunday == "sat-before" and d.weekday() == 6:
            d -= timedelta(days=1)
    else:
        base = _anchor(cat, rule.anchor, year)
        if base is None:
            return None
        d = base
        if wd is not None:
            if rule.direction == "after":
                d = _after(base, wd)
            elif rule.direction == "nearest":
                b, a = _before(base, wd), _after(base, wd)
                d = b if (base - b) <= (a - base) else a
            else:
                d = _before(base, wd)
    return d + timedelta(weeks=rule.weeks, days=rule.days)


def date_for(cat: Catalogue, society_id: str, year: int) -> date | None:
    """The year's known date if there is one, else the rule's date, else None."""
    known = cat.societies[society_id].known_in(year)
    return known.date if known else rule_date(cat, society_id, year)


def _anchor_name(cat: Catalogue, anchor: str) -> str:
    if anchor == "nov5":
        return "5 November"
    if anchor == "remembrance-sunday":
        return "Remembrance Sunday"
    return cat.societies[anchor].name if anchor in cat.societies else anchor


def _offset(weeks: int, days: int) -> str:
    if weeks and not days:
        n = abs(weeks)
        return f"{'a week' if n == 1 else f'{n} weeks'} {'before' if weeks < 0 else 'after'}"
    total = weeks * 7 + days
    n = abs(total)
    return f"{'the day' if n == 1 else f'{n} days'} {'before' if total < 0 else 'after'}"


def describe(cat: Catalogue, rule: Rule | None) -> str:
    """The rule in words: "Wednesday before Firle", "1st Saturday of September"."""
    if rule is None:
        return "no rule yet"
    day = WEEKDAY_NAMES[WEEKDAYS.index(rule.weekday)] if rule.weekday else None
    if rule.nth is not None:
        text = f"{ORDINALS.get(rule.nth, f'{rule.nth}th')} {day} of {calendar.month_name[rule.month]}"
    elif rule.day is not None:
        text = f"{rule.day} {calendar.month_name[rule.month]}"
        if rule.sunday == "sat-before":
            text += " (Saturday before if a Sunday)"
    else:
        name = _anchor_name(cat, rule.anchor)
        base = f"{day} {rule.direction or 'before'} {name}" if day else name
        if rule.weeks or rule.days:
            text = f"{_offset(rule.weeks, rule.days)} {'the ' + base if day else base}"
        else:
            text = base
    return text + (" (a guess)" if rule.guess else "")


def _counterparts(cat: Catalogue, society_id: str):
    """The events whose order this one is held to: (other id, other must come later)."""
    s = cat.societies[society_id]
    if s.kind == "badge" and s.of in cat.societies:
        yield s.of, True  # a badge night comes before its society's night
    for b in cat.societies.values():
        if b.kind == "badge" and b.of == society_id:
            yield b.id, False


def known_clash(cat: Catalogue, society_id: str, day: date) -> tuple[str, date] | None:
    """The other event, and its known date, that `day` would put out of order:
    a badge night always comes before its society's night in the same year
    (though not necessarily just before)."""
    for other, later in _counterparts(cat, society_id):
        k = cat.societies[other].known_in(day.year)
        if k and (k.date <= day if later else k.date >= day):
            return other, k.date
    return None


def out_of_order(cat: Catalogue, society_id: str, year: int) -> tuple[str, date] | None:
    """If this event's predicted date for the year breaks that order, the other
    event and its date; else None. Only a predicted date gives way: a known date
    never does, and when both are predicted the badge night's does."""
    s = cat.societies[society_id]
    day = date_for(cat, society_id, year)
    if day is None or s.known_in(year):
        return None
    for other, later in _counterparts(cat, society_id):
        o = cat.societies[other]
        if o.status != "active":
            continue
        theirs = date_for(cat, other, year) if later else (k.date if (k := o.known_in(year)) else None)
        if theirs and (theirs <= day if later else theirs >= day):
            return other, theirs
    return None
