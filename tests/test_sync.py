from dataclasses import replace
from datetime import date

from click.testing import CliRunner

from bonfire_dates import config, store, sync
from bonfire_dates.calendar_app import FakeCalendar
from bonfire_dates.load import load
from bonfire_dates.model import Catalogue, Evidence, Known
from bonfire_dates.predict import predict_one

TODAY = date(2026, 11, 15)
CAT = load(config.SOCIETIES_FILE, None)


def with_society(cat: Catalogue, sid: str, **changes) -> Catalogue:
    return Catalogue({**cat.societies, sid: replace(cat.societies[sid], **changes)}, cat.badge_confidence)


def keys(cal: FakeCalendar) -> set[str]:
    return {p.key for p in cal.events.values()}


def test_first_sync_writes_rest_of_2026_and_all_2027(tmp_path):
    cal = FakeCalendar()
    result = sync.run(CAT, cal, tmp_path / "state.json", TODAY, dry_run=False)
    assert "barcombe:2026" in keys(cal)
    assert "firle:2026" not in keys(cal)  # already past
    assert "firle:2027" in keys(cal) and "uckfield:2027" in keys(cal)
    assert result.written == len(cal.events) and result.failed == []


def test_second_sync_is_idempotent(tmp_path):
    cal = FakeCalendar()
    sync.run(CAT, cal, tmp_path / "state.json", TODAY, dry_run=False)
    cal.calls.clear()
    result = sync.run(CAT, cal, tmp_path / "state.json", TODAY, dry_run=False)
    assert cal.calls == [] and result.written == 0


def test_text_change_rewrites_event(tmp_path):
    cal = FakeCalendar()
    sync.run(CAT, cal, tmp_path / "state.json", TODAY, dry_run=False)
    renamed = with_society(CAT, "firle", name="Firle village")
    result = sync.run(renamed, cal, tmp_path / "state.json", TODAY, dry_run=False)
    assert result.written == 2  # Firle, and its badge night ("Wednesday before Firle village")
    assert any(p.title.startswith("🔥 Firle village") for p in cal.events.values())


def test_confirmed_date_moves_event(tmp_path):
    cal = FakeCalendar()
    path = tmp_path / "state.json"
    sync.run(CAT, cal, path, TODAY, dry_run=False)
    uid = store.load(path).events["firle:2027"]["uid"]
    firle = CAT.societies["firle"]
    moved = with_society(CAT, "firle", known=(*firle.known, Known(date(2027, 10, 30), Evidence("society"))))
    sync.run(moved, cal, path, TODAY, dry_run=False)
    p = cal.events[uid]
    assert p.day == date(2027, 10, 30)
    assert p.title == "🔥 Firle"
    assert p.notes.startswith("Confidence 100%")
    assert sum(1 for q in cal.events.values() if q.key == "firle:2027") == 1


def test_society_set_unknown_removes_future_event(tmp_path):
    cal = FakeCalendar()
    path = tmp_path / "state.json"
    sync.run(CAT, cal, path, TODAY, dry_run=False)
    result = sync.run(with_society(CAT, "seaford", status="unknown"), cal, path, TODAY, dry_run=False)
    assert "seaford:2027" not in keys(cal) and result.removed == 1
    assert "seaford:2027" not in store.load(path).events


def test_past_events_never_touched(tmp_path):
    cal = FakeCalendar()
    path = tmp_path / "state.json"
    store.save(store.State({"firle:2026": {"uid": "old", "day": "2026-10-24", "hash": "x"}}), path, TODAY)
    cal.events["old"] = predict_one(CAT, "firle", 2026)  # an event written last season
    sync.run(with_society(CAT, "firle", status="gone"), cal, path, TODAY, dry_run=False)
    assert "old" in cal.events and ("remove", "old") not in cal.calls
    assert "firle:2026" in store.load(path).events


def test_failed_write_is_not_recorded_and_retries(tmp_path):
    cal = FakeCalendar()
    cal.fail_keys = {"firle:2027"}
    path = tmp_path / "state.json"
    result = sync.run(CAT, cal, path, TODAY, dry_run=False)
    assert [k for k, _ in result.failed] == ["firle:2027"]
    assert "firle:2027" not in store.load(path).events
    cal.fail_keys = set()
    sync.run(CAT, cal, path, TODAY, dry_run=False)
    assert "firle:2027" in store.load(path).events


def test_dry_run_changes_nothing(tmp_path):
    cal = FakeCalendar()
    path = tmp_path / "state.json"
    result = sync.run(CAT, cal, path, TODAY, dry_run=True)
    assert cal.calls == [] and not path.exists()
    assert result.written > 0  # what it would write


def test_missing_calendar_exits_1_state_unchanged(tmp_path, monkeypatch):
    from bonfire_dates import cli

    cal = FakeCalendar()
    cal.ready = 'Calendar "Bonfire" not found: create it in Calendar.app under your iCloud account'
    monkeypatch.setattr(cli, "make_calendar", lambda: cal)
    monkeypatch.setenv("BONFIRE_DATA_DIR", str(tmp_path))
    result = CliRunner().invoke(cli.cli, ["sync"])
    assert result.exit_code == 1
    assert "Calendar.app" in result.output
    assert not (tmp_path / "state.json").exists() and cal.calls == []


def test_stale_keys_sharing_a_wanted_uid_never_remove_it(tmp_path):
    cal = FakeCalendar()
    path = tmp_path / "state.json"
    sync.run(CAT, cal, path, TODAY, dry_run=False)
    state = store.load(path)
    uid = state.events["firle:2027"]["uid"]
    state.events["old-firle:2027"] = {"uid": uid, "day": "2027-10-23", "hash": "x"}
    state.events["older-firle:2027"] = {"uid": uid, "day": "2027-10-23", "hash": "y"}
    store.save(state, path, TODAY)
    result = sync.run(CAT, cal, path, TODAY, dry_run=False)
    assert uid in cal.events and ("remove", uid) not in cal.calls
    after = store.load(path).events
    assert "old-firle:2027" not in after and "older-firle:2027" not in after
    assert after["firle:2027"]["uid"] == uid and result.failed == []


def test_two_stale_keys_sharing_a_uid_remove_once(tmp_path):
    cal = FakeCalendar()
    path = tmp_path / "state.json"
    store.save(store.State({"a:2027": {"uid": "u", "day": "2027-10-01", "hash": "x"},
                            "b:2027": {"uid": "u", "day": "2027-10-01", "hash": "x"}}), path, TODAY)
    result = sync.run(CAT, cal, path, TODAY, dry_run=False)
    assert cal.calls.count(("remove", "u")) == 1
    assert result.failed == []
    assert not {"a:2027", "b:2027"} & store.load(path).events.keys()
