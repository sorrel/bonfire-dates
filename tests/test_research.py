from datetime import date

import click
import pytest

from bonfire_dates import config, research
from bonfire_dates.load import load
from bonfire_dates.confidence import rate

CAT = load(config.SOCIETIES_FILE, None)


def test_append_confirmed_round_trips_with_escaping(tmp_path):
    path = tmp_path / "confirmed.toml"
    research.append_confirmed(path, "firle", date(2027, 10, 23), "society",
                              'https://example.org/a"b', date(2027, 9, 1))
    research.append_confirmed(path, "newick", date(2027, 10, 30), "verified", None, date(2027, 9, 2))
    cat = load(config.SOCIETIES_FILE, path)
    r = rate(cat, "firle", 2027)
    assert (r.percent, r.confirmed) == (100, True)
    assert r.matches[0].evidence.url == 'https://example.org/a"b'
    assert cat.societies["newick"].known_in(2027).date == date(2027, 10, 30)


def test_file_evidence_never_overwrites(tmp_path):
    src = tmp_path / "poster.jpg"
    src.write_bytes(b"one")
    a = research.file_evidence(tmp_path / "data", "firle", src, date(2026, 11, 15))
    src.write_bytes(b"two")
    b = research.file_evidence(tmp_path / "data", "firle", src, date(2026, 11, 15))
    assert a.name == "2026-11-15-poster.jpg" and b.name == "2026-11-15-poster-2.jpg"
    assert a.read_bytes() == b"one" and b.read_bytes() == b"two"
    assert a.parent == tmp_path / "data" / "evidence" / "firle"


def test_resolve_id_suggests_nearest():
    assert research.resolve_id(CAT, "firle") == "firle"
    with pytest.raises(click.BadParameter) as e:
        research.resolve_id(CAT, "firl")
    assert "firle" in str(e.value)


def test_todo_lists_only_unconfirmed_future():
    items = research.todo(CAT, 2026, date(2026, 11, 15))
    ids = [p.society.id for p in items]
    assert "robertsbridge" not in ids  # 2026 date already known
    assert all(p.day >= date(2026, 11, 15) for p in items)
    items_2027 = research.todo(CAT, 2027, date(2026, 11, 15))
    assert items_2027 and all(not p.confirmed for p in items_2027)


def test_last_checked():
    assert research.last_checked(CAT.societies["buxted"]) == date(2026, 11, 15)
    assert research.last_checked(CAT.societies["uckfield"]) is None
