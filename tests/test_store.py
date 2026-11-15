from datetime import date, timedelta

from bonfire_dates import store


def test_round_trip(tmp_path):
    path = tmp_path / "state.json"
    s = store.State({"firle:2027": {"uid": "u1", "day": "2027-10-23"}})
    store.save(s, path, date(2026, 11, 15))
    assert store.load(path) == s


def test_missing_file_is_empty_state(tmp_path):
    assert store.load(tmp_path / "state.json") == store.State({})


def test_backup_kept_once_per_day_last_30(tmp_path):
    path = tmp_path / "state.json"
    start = date(2026, 1, 1)
    for i in range(40):
        for _ in range(2):  # two saves a day still make one backup
            store.save(store.State({"k": {"uid": str(i), "day": "2027-01-01"}}), path, start + timedelta(days=i))
    backups = sorted((tmp_path / "backups").glob("state-*.json"))
    assert len(backups) == 30
    assert backups[-1].name == f"state-{start + timedelta(days=39)}.json"
