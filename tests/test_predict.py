from datetime import datetime

from bonfire_dates import config
from bonfire_dates.load import load
from bonfire_dates.predict import predictions

from tests.helpers import with_history

CAT = with_history(load(config.SOCIETIES_FILE, None), ["newick", "firle", "firle-badge", "uckfield"], (2024, 2025, 2026))
P2027 = {p.society.id: p for p in predictions(CAT, 2027)}


def test_title_is_plain_whatever_the_percent():
    assert P2027["ninfield"].percent < 70
    assert P2027["ninfield"].title == "🔥 Ninfield"  # the percentage is in the notes and the tables
    assert P2027["ninfield"].notes.startswith(f"Confidence {P2027['ninfield'].percent}%")
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


def test_predicted_badge_after_its_night_is_left_out():
    from datetime import date

    from tests.helpers import with_known
    cat = with_known(CAT, "chiddingly", date(2030, 8, 10), "society")  # before the badge's 3rd Sat Aug
    ids = {p.society.id for p in predictions(cat, 2030)}
    assert "chiddingly" in ids and "chiddingly-badge" not in ids


def test_going_makes_event_timed_with_its_hours():
    from dataclasses import replace
    from datetime import time
    from bonfire_dates.predict import predict_one
    cat = replace(CAT, going={"robertsbridge:2027": (time(18, 0), time(22, 30))})
    p = predict_one(cat, "robertsbridge", 2027)
    assert not p.all_day
    assert p.start == datetime(2027, 11, 20, 18, 0, tzinfo=config.TZ)
    assert p.end == datetime(2027, 11, 20, 22, 30, tzinfo=config.TZ)
    assert p.notes.splitlines()[1] == "Going 18:00–22:30"
    assert predict_one(CAT, "robertsbridge", 2027).all_day  # unmarked: as before


def test_going_past_midnight_ends_next_day():
    from dataclasses import replace
    from datetime import time
    from bonfire_dates.predict import predict_one
    cat = replace(CAT, going={"glynde-parade:2027": (time(18, 0), time(0, 30))})
    p = predict_one(cat, "glynde-parade", 2027)
    assert p.start == datetime(2027, 11, 19, 18, 0, tzinfo=config.TZ)  # hours replace the society's start
    assert p.end == datetime(2027, 11, 20, 0, 30, tzinfo=config.TZ)
