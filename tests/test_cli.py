from click.testing import CliRunner

from bonfire_dates.cli import cli


def test_help_lists_commands():
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Sussex bonfire" in result.output


import json
import shutil

import pytest

from bonfire_dates import config


@pytest.fixture
def confirmed(tmp_path, monkeypatch):
    """A scratch confirmed.toml, so tests never change the real one."""
    path = tmp_path / "confirmed.toml"
    if config.CONFIRMED_FILE.exists():
        shutil.copy(config.CONFIRMED_FILE, path)
    monkeypatch.setattr(config, "CONFIRMED_FILE", path)
    monkeypatch.setenv("BONFIRE_DATA_DIR", str(tmp_path / "data"))
    return path


def run(*args, color=False):
    return CliRunner().invoke(cli, list(args), color=color)


def test_predict_2027_table_has_months_and_percentages(confirmed):
    r = run("predict", "2027")
    assert r.exit_code == 0
    assert "October 2027" in r.output and "Firle" in r.output and "%" in r.output


def test_predict_verbose_shows_rule(confirmed):
    assert "a week before Newick" in run("predict", "2027", "-v").output


def test_predict_json_is_plain(confirmed):
    r = run("predict", "2027", "--json", color=True)
    assert "\x1b" not in r.output
    rows = json.loads(r.output)
    firle = next(x for x in rows if x["society"] == "firle")
    assert firle == {"key": "firle:2027", "society": "firle", "name": "Firle", "date": "2027-10-23",
                     "percent": firle["percent"], "confirmed": False, "rule": "a week before Newick"}
    assert isinstance(firle["percent"], int)


def test_confirm_unknown_id_suggests_and_changes_nothing(confirmed):
    confirmed.write_text("# confirmed dates\n")
    before = confirmed.read_bytes()
    r = run("confirm", "firl", "2027-10-23")
    assert r.exit_code == 2 and "firle" in r.output
    assert confirmed.read_bytes() == before


def test_confirm_appends_and_reloads(confirmed):
    r = run("confirm", "firle", "2027-10-23", "--source", "society", "--url", "https://example.org/p")
    assert r.exit_code == 0, r.output
    assert "100%" in r.output
    assert "firle:2027" in run("predict", "2027", "--json").output
    row = next(x for x in json.loads(run("predict", "2027", "--json").output) if x["society"] == "firle")
    assert row["confirmed"] is True


def test_confirm_rejects_bad_source(confirmed):
    r = run("confirm", "firle", "2027-10-23", "--source", "rumour")
    assert r.exit_code == 2


def test_todo_shows_links(confirmed):
    r = run("todo", "2027")
    assert r.exit_code == 0
    assert "https://www.firlebonfire.co.uk" in r.output.split()  # the whole address, as a word


def test_sources_lists_evidence(confirmed):
    r = run("sources", "glynde-parade")
    assert r.exit_code == 0
    assert "2024" in r.output and "coach list" in r.output and "Friday after Remembrance Sunday" in r.output


def test_evidence_files_locally(confirmed, tmp_path):
    poster = tmp_path / "poster.jpg"
    poster.write_bytes(b"x")
    r = run("evidence", "glynde-parade", str(poster))
    assert r.exit_code == 0
    assert list((tmp_path / "data" / "evidence" / "glynde-parade").iterdir())
    assert "glynde-parade" in run("sources", "glynde-parade").output


def test_check_ok(confirmed):
    r = run("check")
    assert r.exit_code == 0 and "No problems" in r.output


def test_check_reports_problems_exit_1(confirmed):
    confirmed.write_text('[[confirmed]]\nsociety = "nobody"\ndate = 2027-10-23\nsource = "verified"\n')
    r = run("check")
    assert r.exit_code == 1 and "nobody" in r.output


def test_list_shows_unknown_dimmed_when_tty(confirmed):
    r = run("list", color=True)
    assert r.exit_code == 0
    line = next(x for x in r.output.splitlines() if "Cuckfield" in x)
    assert "\x1b[2m" in line


def test_second_confirm_for_same_year_wins(confirmed):
    run("confirm", "firle", "2027-10-30")
    r = run("confirm", "firle", "2027-11-06")
    assert "Sat 06 Nov 2027" in r.output
    row = next(x for x in json.loads(run("predict", "2027", "--json").output) if x["society"] == "firle")
    assert row["date"] == "2027-11-06"


def test_confirm_says_when_a_better_trusted_date_stays(confirmed):
    run("confirm", "firle", "2030-10-26")  # verified, kept privately
    r = run("confirm", "firle", "2030-10-27", "--source", "guide")
    assert r.exit_code == 0
    assert "Sat 26 Oct 2030" in r.output and "better-trusted" in r.output


def test_confirm_verified_goes_to_private_file(confirmed, tmp_path):
    before = confirmed.read_bytes() if confirmed.exists() else b""
    r = run("confirm", "firle", "2027-10-23")
    assert r.exit_code == 0, r.output
    assert (confirmed.read_bytes() if confirmed.exists() else b"") == before
    assert "firle" in (tmp_path / "data" / "known.toml").read_text()
    assert "private" in r.output


def test_confirm_with_public_source_goes_to_public_file(confirmed, tmp_path):
    run("confirm", "firle", "2027-10-23", "--source", "society", "--url", "https://example.org/p")
    assert "firle" in confirmed.read_text()
    assert not (tmp_path / "data" / "known.toml").exists()


def test_unknown_society_error_names_the_argument_as_usage_does():
    r = run("confirm", "firl", "2027-10-23")
    assert r.exit_code != 0
    assert "for SOCIETY:" in r.output and "for ID" not in r.output
