from datetime import datetime

from bonfire_dates import config
from bonfire_dates.load import load
from bonfire_dates.predict import predictions

from tests.helpers import with_history

CAT = with_history(load(config.SOCIETIES_FILE, None), ["newick", "firle", "firle-badge", "uckfield"], (2024, 2025, 2026))
P2027 = {p.society.id: p for p in predictions(CAT, 2027)}


def test_title_marks_uncertain():
    assert P2027["ninfield"].title == "🔥 Ninfield?"
    assert P2027["uckfield"].title == "🔥 Uckfield"


def test_emoji_by_kind():
    assert P2027["firle-badge"].title == "🦡 Firle badge night"
    assert P2027["lewes-fancy-dress"].title.startswith("🎭 ")
    assert P2027["glynde-parade"].title.startswith("🕯️ ")


def test_notes_start_with_confidence_then_rule_then_evidence():
    notes = P2027["firle"].notes.splitlines()
    assert notes[0] == "Confidence 92%"
    assert "a week before Newick" in notes[1]
    assert any("2024" in line and "verified" in line for line in notes)  # generated history
    assert notes[-1] == "Predicted, not published."


def test_timed_vs_all_day():
    parade = P2027["glynde-parade"]
    assert not parade.all_day
    assert parade.start == datetime(2027, 11, 19, 19, 30, tzinfo=config.TZ)
    assert parade.end == datetime(2027, 11, 19, 22, 30, tzinfo=config.TZ)
    uck = P2027["uckfield"]
    assert uck.all_day
    assert uck.start == datetime(2027, 9, 4, tzinfo=config.TZ)
    assert uck.end == datetime(2027, 9, 5, tzinfo=config.TZ)


def test_keys():
    assert P2027["firle"].key == "firle:2027"


def test_sorted_by_day_then_name():
    days = [p.day for p in predictions(CAT, 2027)]
    assert days == sorted(days)


def test_unknown_and_ruleless_societies_have_no_prediction():
    assert "cuckfield" not in P2027
    assert "hawkhurst" not in P2027
    from tests.helpers import with_known
    from datetime import date
    known = with_known(CAT, "hawkhurst", date(2030, 11, 8), "society")
    assert "hawkhurst" in {p.society.id for p in predictions(known, 2030)}  # a known date, no rule
