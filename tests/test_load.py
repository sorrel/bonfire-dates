from datetime import date, time
from pathlib import Path

import pytest

from bonfire_dates.load import DataError, load

TWO = """
[defaults]
badge_confidence = 10

[newick]
name = "Newick"
kind = "night"
status = "active"
place = "Newick, East Sussex"
rule = { anchor = "nov5", weekday = "sat", direction = "before" }
known = [ { date = 2030-11-02, source = "society" } ]

[firle]
name = "Firle"
kind = "night"
status = "active"
place = "Firle, East Sussex"
start = "18:00"
links = { website = "https://example.org/firle" }
rule = { anchor = "newick", weeks = -1 }
known = [ { date = 2030-10-26, source = "society" } ]
"""


def write(tmp_path: Path, text: str, name: str = "societies.toml") -> Path:
    p = tmp_path / name
    p.write_text(text)
    return p


def test_loads_rule_known_and_links(tmp_path):
    cat = load(write(tmp_path, TWO), None)
    firle = cat.societies["firle"]
    assert firle.rule.anchor == "newick"
    assert firle.rule.weeks == -1
    assert firle.known[0].date == date(2030, 10, 26)
    assert firle.known[0].evidence.source == "society"
    assert firle.links["website"] == "https://example.org/firle"
    assert firle.start == time(18, 0)
    assert cat.badge_confidence == 10


def test_confirmed_file_merges_into_known(tmp_path):
    confirmed = write(tmp_path, """
[[confirmed]]
society = "firle"
date = 2027-10-23
source = "society"
url = "https://example.org/poster"
checked = 2027-09-01
""", "confirmed.toml")
    cat = load(write(tmp_path, TWO), confirmed)
    k = [k for k in cat.societies["firle"].known if k.date == date(2027, 10, 23)][0]
    assert k.evidence.source == "society"
    assert k.evidence.url == "https://example.org/poster"
    assert k.evidence.checked == date(2027, 9, 1)


def test_missing_confirmed_file_is_fine(tmp_path):
    cat = load(write(tmp_path, TWO), tmp_path / "confirmed.toml")
    assert len(cat.societies["firle"].known) == 1


def test_syntax_error_is_a_data_error(tmp_path):
    with pytest.raises(DataError) as e:
        load(write(tmp_path, "[firle\nname = 1"), None)
    assert "societies.toml" in str(e.value)
    assert "line" in str(e.value)


def test_unknown_anchor_unknown_source_and_cycle_all_reported(tmp_path):
    bad = """
[a]
name = "A"
kind = "night"
status = "active"
rule = { anchor = "nowhere" }
known = [ { date = 2026-10-31, source = "rumour" } ]

[b]
name = "B"
kind = "night"
status = "active"
rule = { anchor = "c", weeks = 1 }

[c]
name = "C"
kind = "night"
status = "active"
rule = { anchor = "b", weeks = -1 }
"""
    with pytest.raises(DataError) as e:
        load(write(tmp_path, bad), None)
    problems = e.value.problems
    assert len(problems) == 3
    assert any("a" in p and "nowhere" in p for p in problems)
    assert any("a" in p and "rumour" in p for p in problems)
    assert any("cycle" in p and "b" in p and "c" in p for p in problems)


def test_confirmed_for_unknown_society_is_a_problem(tmp_path):
    confirmed = write(tmp_path, '[[confirmed]]\nsociety = "nobody"\ndate = 2027-10-23\nsource = "verified"\n',
                      "confirmed.toml")
    with pytest.raises(DataError) as e:
        load(write(tmp_path, TWO), confirmed)
    assert any("nobody" in p for p in e.value.problems)


BASE = '[s]\nname = "S"\nkind = "night"\nstatus = "active"\n'


@pytest.mark.parametrize(("extra", "words"), [
    ('rule = { month = 13, weekday = "sat", nth = 1 }', "month"),
    ("rule = { month = 2, day = 30 }", "day"),
    ('rule = { month = 9, weekday = "sat", nth = "1" }', "nth"),
    ('rule = { month = 9, weekday = "sat", nth = 0 }', "nth"),
    ('rule = { anchor = "nov5", weeks = "1" }', "weeks"),
    ('rule = "first sat"', "rule"),
    ('links = "http://x"', "links"),
    ('known = ["2025-01-01"]', "known"),
    ("confidence = true", "confidence"),
])
def test_bad_values_are_data_errors_not_crashes(tmp_path, extra, words):
    with pytest.raises(DataError) as e:
        load(write(tmp_path, BASE + extra + "\n"), None)
    assert any(words in p and "[s]" in p for p in e.value.problems)


def test_name_must_be_text(tmp_path):
    with pytest.raises(DataError):
        load(write(tmp_path, BASE.replace('name = "S"', "name = 5")), None)


def test_feb_29_rule_is_allowed(tmp_path):
    load(write(tmp_path, BASE + "rule = { month = 2, day = 29 }\n"), None)


def test_top_level_scalar_and_bad_defaults(tmp_path):
    with pytest.raises(DataError) as e:
        load(write(tmp_path, 'foo = 1\n[defaults]\nbadge_confidence = "x"\n' + BASE), None)
    assert any("foo" in p for p in e.value.problems)
    assert any("badge_confidence" in p for p in e.value.problems)


def test_unreadable_file_is_a_data_error(tmp_path):
    p = tmp_path / "societies.toml"
    p.write_bytes(b"\xff\xfe[bad")
    with pytest.raises(DataError):
        load(p, None)
    with pytest.raises(DataError):
        load(tmp_path / "missing.toml", None)


def test_catalogue_problems_name_the_file(tmp_path):
    with pytest.raises(DataError) as e:
        load(write(tmp_path, BASE + 'rule = { anchor = "zz" }\n'), None)
    assert e.value.problems[0].startswith("societies.toml: [s]")


def test_private_known_file_merges_like_confirmed(tmp_path):
    local = write(tmp_path, '[[confirmed]]\nsociety = "firle"\ndate = 2031-10-25\nsource = "verified"\n',
                  "known.toml")
    cat = load(write(tmp_path, TWO), None, local)
    assert date(2031, 10, 25) in [k.date for k in cat.societies["firle"].known]


def test_searched_is_the_day_sources_were_last_looked_for(tmp_path):
    text = TWO.replace('start = "18:00"', 'start = "18:00"\nsearched = 2026-11-16')
    cat = load(write(tmp_path, text), None)
    assert cat.societies["firle"].searched == date(2026, 11, 16)
    assert cat.societies["newick"].searched is None


def test_searched_must_be_a_date(tmp_path):
    with pytest.raises(DataError, match="searched must be a date"):
        load(write(tmp_path, TWO.replace('start = "18:00"', 'start = "18:00"\nsearched = "recently"')), None)


def test_visiting_society_loads_without_rule(tmp_path):
    cat = load(write(tmp_path, BASE.replace('"night"', '"visiting"')), None)
    assert cat.societies["s"].kind == "visiting"


@pytest.mark.parametrize("extra", [
    'rule = { month = 9, weekday = "sat", nth = 1 }',
    "known = [ { date = 2030-11-02, source = \"society\" } ]",
])
def test_visiting_society_may_not_have_dates(tmp_path, extra):
    with pytest.raises(DataError, match="no event of its own"):
        load(write(tmp_path, BASE.replace('"night"', '"visiting"') + extra + "\n"), None)


def test_known_badge_date_after_its_known_night_is_a_problem(tmp_path):
    text = TWO + """
[firle-badge]
name = "Firle badge night"
kind = "badge"
status = "active"
of = "firle"
known = [ { date = 2030-10-26, source = "society" } ]
"""
    with pytest.raises(DataError, match="must come before"):
        load(write(tmp_path, text), None)


GOING = """
[[going]]
society = "newick"
year = 2030
from = "18:00"
to = "22:30"
"""


def test_going_entry_loads(tmp_path):
    cat = load(write(tmp_path, TWO), None, going_path=write(tmp_path, GOING, "going.toml"))
    assert cat.going == {"newick:2030": (time(18, 0), time(22, 30))}


def test_going_missing_file_is_no_marks(tmp_path):
    assert load(write(tmp_path, TWO), None, going_path=tmp_path / "going.toml").going == {}


def test_going_problems_collected(tmp_path):
    bad = """
[[going]]
society = "nobody"
year = 2030
from = "18:00"
to = "22:30"

[[going]]
society = "newick"
year = "soon"
from = "late"
to = "22:30"
"""
    with pytest.raises(DataError) as e:
        load(write(tmp_path, TWO), None, going_path=write(tmp_path, bad, "going.toml"))
    text = "\n".join(e.value.problems)
    assert "unknown society 'nobody'" in text
    assert "year must be" in text
    assert "from must be a time" in text
