import json
import sys

from bonfire_dates import calendar_app, config
from bonfire_dates.calendar_app import CalendarError, Change, FakeCalendar, MacCalendar
from bonfire_dates.load import load
from bonfire_dates.predict import predictions

CAT = load(config.SOCIETIES_FILE, None)
P = {p.society.id: p for p in predictions(CAT, 2027)}


def stand_in(tmp_path, body: str) -> MacCalendar:
    """A MacCalendar whose script is a small Python program: never the real calendar."""
    script = tmp_path / "fake.py"
    script.write_text("import json, sys, time\nreq = json.load(sys.stdin)\n" + body)
    return MacCalendar("Bonfire", [sys.executable, str(script)])


def test_payload_all_day_and_no_alarms():
    p = calendar_app.payload(Change(None, P["uckfield"]))
    assert p["allDay"] is True
    assert p["alarms"] == []
    assert p["key"] == "uckfield:2027"
    assert p["location"] == "Uckfield, East Sussex"
    timed = calendar_app.payload(Change("u1", P["glynde-parade"]))
    assert timed["allDay"] is False and timed["uid"] == "u1"


def test_mac_calendar_with_stand_in_command(tmp_path):
    seen = tmp_path / "seen.json"
    cal = stand_in(tmp_path, f"open({str(seen)!r}, 'w').write(json.dumps(req))\n"
                             "for _ in req['ops']: print(json.dumps({'ok': True, 'uid': 'u1'}), flush=True)\n")
    assert cal.apply([Change(None, P["firle"])]) == ["u1"]
    sent = json.loads(seen.read_text())
    assert sent["calendar"] == "Bonfire"
    assert sent["ops"][0]["title"].startswith("🔥 Firle")


def test_mac_reports_each_failure(tmp_path):
    cal = stand_in(tmp_path, "print(json.dumps({'ok': False, 'error': 'event x is in another calendar'}))\n")
    [r] = cal.apply([Change("x", P["firle"])])
    assert isinstance(r, CalendarError) and "another calendar" in str(r)


def test_mac_missing_calendar_message(tmp_path):
    cal = stand_in(tmp_path, "print(json.dumps({'ok': False, 'error': 'missing'}))\n")
    assert "Calendar.app" in cal.check_ready()


def test_mac_script_crash_is_an_error_not_a_hang(tmp_path):
    cal = stand_in(tmp_path, "sys.stderr.write('boom'); sys.exit(1)\n")
    [r] = cal.apply([Change(None, P["firle"])])
    assert isinstance(r, CalendarError) and "boom" in str(r)


def test_calendar_script_refuses_other_calendars_and_handles_all_day():
    js = calendar_app.SCRIPT.read_text()
    assert "in another calendar: refusing to touch it" in js
    assert "MARK = 'bonfire-dates:'" in js
    assert "allDay" in js


def test_fake_keeps_one_event_per_key():
    cal = FakeCalendar()
    [a] = cal.apply([Change(None, P["firle"])])
    [b] = cal.apply([Change(None, P["firle"])])  # reply lost: no uid known, same key
    assert a == b and len(cal.events) == 1


def test_all_day_end_equals_start_so_eventkit_sets_one_day():
    p = calendar_app.payload(Change(None, P["uckfield"]))
    assert p["end"] == p["start"]
    timed = calendar_app.payload(Change(None, P["glynde-parade"]))
    assert timed["end"] - timed["start"] == 3 * 3600 * 1000
