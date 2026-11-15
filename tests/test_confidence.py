from datetime import date

import pytest

from bonfire_dates import config
from bonfire_dates.confidence import rate
from bonfire_dates.load import load
from tests.helpers import with_history, with_known

PUBLIC = load(config.SOCIETIES_FILE, None)
THREE = (2024, 2025, 2026)
CAT = with_history(PUBLIC, ["uckfield", "newick", "firle", "firle-badge", "lewes", "lewes-badge"], THREE)
CAT = with_history(CAT, ["mayfield"], (2025, 2026))


@pytest.mark.parametrize(("sid", "percent"), [
    ("uckfield", 92), ("firle", 92), ("mayfield", 75), ("firle-badge", 92), ("lewes-badge", 92),
    ("lewes", 100), ("ninfield-badge", 10), ("chiddingly-badge", 10), ("glynde-membership", 10),
])
def test_2027_percentages(sid, percent):
    assert rate(CAT, sid, 2027).percent == percent


def test_trusted_contradiction_caps_at_60():
    cat = with_known(with_history(PUBLIC, ["barcombe"], (2024, 2026)), "barcombe", date(2025, 11, 29))
    r = rate(cat, "barcombe", 2027)
    assert r.percent == 60
    assert [k.date for k in r.contradictions] == [date(2025, 11, 29)]


def test_public_data_alone_rates_lower():
    assert rate(PUBLIC, "uckfield", 2027).percent == 25
    assert rate(PUBLIC, "buxted", 2027).percent == 56  # its own site's rule, plus one guide


def test_guess_is_capped():
    assert rate(CAT, "nevill", 2027).percent <= 35


def test_known_date_makes_it_confirmed_100():
    r = rate(with_known(CAT, "firle", date(2027, 10, 30), "society"), "firle", 2027)
    assert (r.percent, r.confirmed) == (100, True)


def test_tradition_can_be_certain_but_is_not_confirmed():
    r = rate(CAT, "lewes", 2027)
    assert (r.percent, r.confirmed) == (100, False)  # no ✓: no source has published it
