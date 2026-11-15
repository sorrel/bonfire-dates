"""The real societies.toml: it loads cleanly, gives the 2027 dates reviewed in
the design's appendix, and says nothing about who saw what."""
from datetime import date

import pytest

from bonfire_dates import config
from bonfire_dates.load import load, problems
from bonfire_dates.rules import date_for

CAT = load(config.SOCIETIES_FILE, None)

APPENDIX_2027 = [
    ("chiddingly-badge", 8, 21), ("uckfield", 9, 4), ("crowborough", 9, 11), ("fletching", 9, 11),
    ("mayfield", 9, 18), ("buxted", 9, 25), ("burgess-hill", 9, 25), ("eastbourne", 10, 2),
    ("northiam", 10, 2), ("rotherfield", 10, 2), ("lewes-fancy-dress", 10, 8), ("heathfield", 10, 9),
    ("nevill-badge", 10, 10), ("hastings", 10, 16), ("hailsham", 10, 16), ("seaford", 10, 16),
    ("east-grinstead", 10, 16), ("firle-badge", 10, 20), ("ninfield-badge", 10, 20), ("firle", 10, 23),
    ("littlehampton", 10, 23), ("ninfield", 10, 23), ("nevill", 10, 23), ("isfield", 10, 29),
    ("newick", 10, 30), ("ewhurst-staplecross", 10, 30), ("lewes-badge", 11, 4), ("lewes", 11, 5),
    ("battle", 11, 6), ("chailey", 11, 6), ("east-hoathly", 11, 13), ("rye", 11, 13),
    ("south-heighton", 11, 13), ("glynde-membership", 11, 17), ("glynde-parade", 11, 19),
    ("barcombe", 11, 20), ("robertsbridge", 11, 20), ("chiddingly", 11, 27),
    ("lindfield", 11, 5),
]


@pytest.mark.parametrize(("sid", "month", "day"), APPENDIX_2027)
def test_2027_dates_match_appendix(sid, month, day):
    assert date_for(CAT, sid, 2027) == date(2027, month, day)


def test_hawkhurst_has_no_2027_date():
    assert date_for(CAT, "hawkhurst", 2027) is None


def test_every_active_entry_is_in_the_appendix_or_ruleless():
    covered = {sid for sid, _, _ in APPENDIX_2027} | {"hawkhurst"}
    active = {s.id for s in CAT.societies.values() if s.status == "active"}
    assert active == covered


def test_known_dates_reproduce_for_their_years():
    assert date_for(CAT, "firle", 2026) == date(2026, 10, 24)
    assert date_for(CAT, "robertsbridge", 2026) == date(2026, 11, 21)


def test_seed_has_no_problems():
    assert problems(CAT) == []


def test_seed_is_neutral():
    for path in (config.SOCIETIES_FILE, config.CONFIRMED_FILE):
        text = path.read_text().lower()
        for word in ("observed", "went", "attended", "/users/", "@", '"verified"'):
            assert word not in text, (path.name, word)


def test_bexhill_is_not_listed():
    assert "bexhill" not in CAT.societies  # there is no Bexhill society


def test_isfield_is_the_last_friday_of_october():
    assert date_for(CAT, "isfield", 2024) == date(2024, 10, 25)
    assert date_for(CAT, "isfield", 2027) == date(2027, 10, 29)


def test_rules_now_backed_by_evidence_are_not_guesses():
    assert not CAT.societies["rotherfield"].rule.guess


def test_doubtful_rules_are_guesses():
    assert CAT.societies["south-heighton"].rule.guess and CAT.societies["nevill"].rule.guess


def test_lindfield_is_5_november_or_the_saturday_before():
    assert date_for(CAT, "lindfield", 2027) == date(2027, 11, 5)
    assert date_for(CAT, "lindfield", 2028) == date(2028, 11, 4)  # the 5th is a Sunday
