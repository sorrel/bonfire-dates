"""How sure a prediction is, as a percentage, from the evidence behind its rule.

1. A known date for the year: 100, confirmed.
2. A `confidence` override in the data: that value.
3. A badge night not marked `rate_on_evidence`: the catalogue's badge default.
4. Otherwise s = the summed weight of matching evidence (known dates from other
   years that the rule reproduces, plus the rule's own evidence), and the
   percent is min(92, 25 + 25·s), capped at 60 if a verified or society date
   contradicts the rule and at 35 if the rule is a guess. Always 1–99.
"""
from dataclasses import dataclass, field

from .model import Catalogue, Known
from .rules import rule_date

WEIGHTS = {"verified": 1.0, "society": 0.9, "guides": 0.6, "guide": 0.35, "wiki": 0.25}
CEILING = 92
CONTRADICTED_CAP = 60
GUESS_CAP = 35
TRUSTED = ("verified", "society")


@dataclass(frozen=True)
class Rating:
    percent: int
    confirmed: bool
    why: str
    matches: list[Known] = field(default_factory=list)
    contradictions: list[Known] = field(default_factory=list)


def rate(cat: Catalogue, society_id: str, year: int) -> Rating:
    s = cat.societies[society_id]
    if known := s.known_in(year):
        return Rating(100, True, f"confirmed ({known.evidence.source})", [known])
    if s.confidence is not None:
        return Rating(min(s.confidence, 99), False, s.why or "set by hand")
    if s.kind == "badge" and not s.rate_on_evidence:
        return Rating(cat.badge_confidence, False, "badge nights are rarely fixed far ahead")
    matches, contradictions = [], []
    for k in s.known:
        if k.date.year != year:
            (matches if rule_date(cat, society_id, k.date.year) == k.date else contradictions).append(k)
    weight = sum(WEIGHTS[k.evidence.source] for k in matches)
    if s.rule and s.rule.evidence:
        weight += WEIGHTS[s.rule.evidence.source]
    percent = min(CEILING, round(25 + 25 * weight))
    why = f"rule fits {len(matches)} known year{'s' if len(matches) != 1 else ''}"
    if any(k.evidence.source in TRUSTED for k in contradictions):
        percent = min(percent, CONTRADICTED_CAP)
        why += f", misses {len(contradictions)}"
    if s.rule and s.rule.guess:
        percent = min(percent, GUESS_CAP)
        why += ", rule is a guess"
    return Rating(max(1, min(99, percent)), False, why, matches, contradictions)
