"""Test-only helpers. History is generated from the rules, never typed in."""
from dataclasses import replace
from datetime import date

from bonfire_dates.model import Catalogue, Evidence, Known
from bonfire_dates.rules import rule_date


def with_history(cat: Catalogue, society_ids: list[str], years: tuple[int, ...],
                 source: str = "verified") -> Catalogue:
    """Give each society known dates that its rule reproduces, for the given years."""
    societies = dict(cat.societies)
    for sid in society_ids:
        temp = Catalogue(societies, cat.badge_confidence)
        added = tuple(Known(d, Evidence(source)) for y in years if (d := rule_date(temp, sid, y)))
        societies[sid] = replace(societies[sid], known=(*societies[sid].known, *added))
    return Catalogue(societies, cat.badge_confidence)


def with_known(cat: Catalogue, sid: str, day: date, source: str = "verified") -> Catalogue:
    s = cat.societies[sid]
    return Catalogue({**cat.societies, sid: replace(s, known=(*s.known, Known(day, Evidence(source))))},
                     cat.badge_confidence)
