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
    assert any(word == "https://www.firlebonfire.co.uk" for word in r.output.split())  # the whole address


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


def test_list_shows_inactive_dimmed_when_tty(confirmed):
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


def test_default_year_is_the_season_being_predicted(confirmed):
    from datetime import date
    from bonfire_dates.cli import catalogue, default_year
    assert default_year(catalogue(), date(2026, 11, 15)) == 2027
    assert default_year(catalogue(), date(2026, 10, 1)) == 2026


def _rows_after(out: str, header_start: str) -> list[str]:
    lines = out.splitlines()
    i = next(n for n, line in enumerate(lines) if line.strip().startswith(header_start))
    rows = []
    for line in lines[i + 2:]:  # skip the header and its rule
        if not line.strip():
            break
        rows.append(line)
    return rows


def test_todo_is_an_aligned_table(confirmed):
    out = run("todo", "2027").output
    assert "Date" in out and "Checked" in out and "Where to look" in out
    rows = _rows_after(out, "Date")
    from bonfire_dates.display import width
    import re
    sure_col = {width(r[:m.start()]) for r in rows if (m := re.search(r"\b\d+%", r))}
    assert len(rows) > 10 and len(sure_col) == 1  # every percentage starts in the same column
    assert not [line for line in out.splitlines() if line != line.rstrip()]


def test_sources_shows_rating_and_a_table_of_dates(confirmed):
    out = run("sources", "glynde-parade").output
    assert "rated" in out and "%" in out
    rows = _rows_after(out, "Date")
    assert any("2024" in r and "guide" in r for r in rows)
    assert not [line for line in out.splitlines() if line != line.rstrip()]


# --- Help that reads easily -------------------------------------------------

def test_top_help_groups_commands_by_task_without_truncation():
    out = run("--help").output
    sections = ["See the season", "Keep the calendar", "Record news", "Look after the data"]
    assert all(s in out for s in sections)
    assert [out.index(s) for s in sections] == sorted(out.index(s) for s in sections)
    assert not [line for line in out.splitlines()[1:] if "..." in line]  # no description cut short
    assert "Typical round" in out and "bonfire confirm" in out


def test_short_h_works_everywhere():
    assert run("-h").exit_code == 0
    assert run("sync", "-h").exit_code == 0


def test_command_help_explains_arguments_with_examples():
    out = run("confirm", "--help").output
    assert "SOCIETY" in out and "bonfire list" in out  # where to find ids
    assert "Examples" in out and "bonfire confirm firle 2027-10-23" in out
    for cmd in ("sync", "predict", "todo", "sources", "evidence", "list", "check"):
        assert "Examples" in run(cmd, "--help").output, cmd


def test_list_shows_ids(confirmed):
    out = run("list").output
    assert "ID" in out and "firle-badge" in out


def test_help_headings_are_bold_on_a_terminal():
    out = run("--help", color=True).output
    assert "\x1b[1m" in out  # bold


def test_help_columns_line_up_across_sections():
    import re
    out = run("--help").output
    starts = {m.start(2) for line in out.splitlines() if (m := re.match(r"  (predict|todo|list|sync|confirm|sources|evidence|check) +(\S)", line))}
    assert len(starts) == 1


def test_examples_put_each_command_on_its_own_line():
    out = run("confirm", "-h").output
    assert "\n\n\n" not in out
    lines = out.splitlines()
    i = next(n for n, line in enumerate(lines) if line.strip() == "bonfire confirm firle 2027-10-23")
    assert lines[i - 1].strip().endswith(":")  # its description sits above it
    assert "SOURCE" in out and "verified|society" not in out


def test_list_is_compact(confirmed):
    out = run("list").output
    from bonfire_dates.display import width
    assert max(width(line) for line in out.splitlines()) <= 150  # was 157, with a Kind column
    assert "🦡 Firle badge night" in out and "unknown" in out
    assert "Kind" not in out


def test_sources_says_when_sources_were_last_searched(confirmed):
    out = run("sources", "crowborough").output
    assert "Searched" in out


def test_sources_labels_line_up_and_never_touch_their_values(confirmed):
    out = run("sources", "fletching").output
    labelled = [line for line in out.splitlines() if line.split()[:1] in (["Rule"], ["Website"], ["Searched"])]
    assert len(labelled) == 3
    assert len({line.index(line.split()[1]) for line in labelled}) == 1  # values share one column


def test_list_shows_visiting_society(confirmed):
    r = run("list")
    line = next(x for x in r.output.splitlines() if "Who the Devil" in x)
    assert "who-the-devil" in line and "no event of its own" in line


def test_confirm_refuses_a_visiting_society(confirmed):
    before = confirmed.read_text() if confirmed.exists() else ""
    r = run("confirm", "who-the-devil", "2027-11-05", "--source", "society")
    assert r.exit_code != 0 and "no event of its own" in r.output
    assert (confirmed.read_text() if confirmed.exists() else "") == before


def test_confirm_refuses_a_badge_date_after_its_night(confirmed):
    run("confirm", "chiddingly", "2030-11-23", "--source", "society")
    before = confirmed.read_text()
    r = run("confirm", "chiddingly-badge", "2030-11-30", "--source", "society")
    assert r.exit_code != 0 and "before" in r.output
    assert confirmed.read_text() == before


def test_confirm_refuses_a_night_date_before_its_badge(confirmed):
    run("confirm", "chiddingly-badge", "2030-08-17", "--source", "society")
    r = run("confirm", "chiddingly", "2030-08-17", "--source", "society")
    assert r.exit_code != 0 and "before" in r.output
