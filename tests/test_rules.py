from datetime import date

from bonfire_dates.model import Catalogue, Evidence, Known, Rule, Society
from bonfire_dates.rules import date_for, describe, rule_date


def cat(*societies: Society) -> Catalogue:
    return Catalogue({s.id: s for s in societies})


def soc(sid: str, rule: Rule | None, name: str | None = None, known=()) -> Society:
    return Society(sid, name or sid.title(), "night", "active", rule=rule, known=tuple(known))


UCKFIELD = soc("uckfield", Rule(month=9, weekday="sat", nth=1))
BURGESS = soc("burgess", Rule(month=9, weekday="sat", nth=-1))
LEWES = soc("lewes", Rule(month=11, day=5, sunday="sat-before"))
BATTLE = soc("battle", Rule(anchor="nov5", weekday="sat", direction="after"))
NEWICK = soc("newick", Rule(anchor="nov5", weekday="sat", direction="before"))
HOATHLY = soc("hoathly", Rule(anchor="remembrance-sunday", weekday="sat", direction="before"))
FIRLE = soc("firle", Rule(anchor="newick", weeks=-1))
LEWES_BADGE = soc("lewes-badge", Rule(anchor="lewes", days=-1))
FIRLE_BADGE = soc("firle-badge", Rule(anchor="firle", weekday="wed", direction="before"), "Firle badge night")
ALL = cat(UCKFIELD, BURGESS, LEWES, BATTLE, NEWICK, HOATHLY, FIRLE, LEWES_BADGE, FIRLE_BADGE)


def test_nth_and_last_weekday():
    assert date_for(ALL, "uckfield", 2027) == date(2027, 9, 4)
    assert date_for(ALL, "burgess", 2027) == date(2027, 9, 25)


def test_lewes_sunday_rule():
    assert date_for(ALL, "lewes", 2027) == date(2027, 11, 5)
    assert date_for(ALL, "lewes", 2028) == date(2028, 11, 4)


def test_anchor_weekday_direction():
    assert date_for(ALL, "battle", 2027) == date(2027, 11, 6)
    assert date_for(ALL, "battle", 2028) == date(2028, 11, 11)
    assert date_for(ALL, "newick", 2027) == date(2027, 10, 30)
    assert date_for(ALL, "hoathly", 2027) == date(2027, 11, 13)


def test_anchor_on_society_with_weeks_and_days():
    assert date_for(ALL, "firle", 2027) == date(2027, 10, 23)
    assert date_for(ALL, "lewes-badge", 2028) == date(2028, 11, 3)
    assert date_for(ALL, "firle-badge", 2027) == date(2027, 10, 20)


def test_nearest_picks_closer_side_and_earlier_on_tie():
    c = cat(soc("n", Rule(anchor="nov5", weekday="sat", direction="nearest")))
    assert date_for(c, "n", 2027) == date(2027, 11, 6)  # Fri 5th: Sat 6th is one day on
    assert date_for(c, "n", 2026) == date(2026, 11, 7)  # Thu 5th: Sat 7th (2 days) beats Sat 31 Oct (5)


def test_known_date_wins_for_its_year():
    moved = soc("firle", Rule(anchor="newick", weeks=-1),
                known=[Known(date(2027, 10, 30), Evidence("society"))])
    c = cat(NEWICK, moved)
    assert date_for(c, "firle", 2027) == date(2027, 10, 30)
    assert rule_date(c, "firle", 2027) == date(2027, 10, 23)


def test_dependent_follows_anchors_known_date():
    newick_moved = soc("newick", NEWICK.rule, known=[Known(date(2027, 11, 6), Evidence("society"))])
    c = cat(newick_moved, FIRLE)
    assert date_for(c, "firle", 2027) == date(2027, 10, 30)


def test_no_rule_is_none():
    c = cat(soc("hawkhurst", None))
    assert date_for(c, "hawkhurst", 2027) is None


def test_describe():
    assert describe(ALL, FIRLE_BADGE.rule) == "Wednesday before Firle"
    assert describe(ALL, UCKFIELD.rule) == "1st Saturday of September"
    assert describe(ALL, BURGESS.rule) == "last Saturday of September"
    assert describe(ALL, LEWES.rule) == "5 November (Saturday before if a Sunday)"
    assert describe(ALL, FIRLE.rule) == "a week before Newick"
    assert describe(ALL, LEWES_BADGE.rule) == "the day before Lewes"
    assert describe(ALL, HOATHLY.rule) == "Saturday before Remembrance Sunday"


def test_feb_29_rule_is_none_in_a_common_year():
    c = cat(soc("leap", Rule(month=2, day=29)))
    assert date_for(c, "leap", 2028) == date(2028, 2, 29)
    assert date_for(c, "leap", 2027) is None


def test_later_entry_of_equal_trust_wins():
    s = soc("x", None, known=[Known(date(2027, 10, 30), Evidence("verified")),
                              Known(date(2027, 11, 6), Evidence("verified")),
                              Known(date(2027, 11, 13), Evidence("guide"))])
    assert s.known_in(2027).date == date(2027, 11, 6)
