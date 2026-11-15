# bonfire-dates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A CLI, `bonfire`, that predicts each Sussex bonfire society's night (plus badge nights and linked events) from hand-written rules, rates each prediction as a percentage, and keeps a dedicated "Bonfire" iCloud calendar in step.

**Architecture:** Public facts live in two tracked TOML files: `societies.toml` (hand-edited) and `confirmed.toml` (appended to by `bonfire confirm`). They load into a `Catalogue`. A rules engine turns each society's rule into a date for a year, and a confidence module rates the date from the society's known dates. `sync` writes the predictions to the calendar through an EventKit bridge copied from albion-tickets. Local state (event IDs, evidence files, backups) lives in gitignored `data/`.

**Tech Stack:** Python ≥ 3.15, uv, Click (the only runtime dependency), `tomllib`, pytest, JXA/EventKit via `osascript`.

**Spec:** `docs/superpowers/specs/2026-11-15-bonfire-dates-design.md`

## Global Constraints

- Repo at `~/Developer/Program/scripts/bonfire-dates`. Package in `src/bonfire_dates/`; `[tool.hatch.build.targets.wheel] packages = ["src/bonfire_dates"]`; `[tool.pytest.ini_options] pythonpath = ["src", "."]`.
- `requires-python = ">=3.15"`; `dependencies = ["click>=8.0.0"]` only. No TOML writer library: `confirmed.toml` is appended as text.
- British English in all copy, comments and docs.
- No personal information in any tracked file: no names, addresses, emails, `/Users/...` paths, or calendar names other than "Bonfire". Date sources say how a date is known (`verified`, `society`, `guides`, `guide`, `wiki`), never by whom. Nothing may reveal which societies the user belongs to or attends.
- Only the "Bonfire" calendar is ever changed. `calendar.js` refuses an event ID found in any other calendar.
- Tests never touch the real calendar or the network (`FakeCalendar`, or `MacCalendar` with a stand-in command).
- Terminal output is designed: bold headings, dim boilerplate, colour on the values, widths measured on plain text with styling applied afterwards, plain output when piped or with `--json`.
- Commits are signed as the user (the git config does this). Never override identity or signing. If signing fails (1Password locked), stop and leave the work staged.
- The first commit (scaffold, spec, plan) goes on `main`; all later tasks go on branch `feat/first-version`.
- Do not create the GitHub repo or push. Publishing is a separate step after the user's review.

## Review Focus

1. **A mistyped society id** in `confirm`, `sources` or `evidence` (e.g. `firl`): expect a clear error naming the nearest ids, and no file changes. Pinned in Task 6.
2. **A year where 5 November is a Sunday** (2028): Lewes moves to Sat 4 Nov, its badge night to Fri 3 Nov, and Battle to Sat 11 Nov. Pinned in Task 3.
3. **The calendar missing or access denied** during `sync`: expect the albion-style message, exit code 1, and `state.json` unchanged. Pinned in Task 5.
4. **A malformed or inconsistent data file** (TOML syntax error, unknown anchor, anchor cycle, unknown source): expect one readable error per problem, with file and society id, and exit code 1, never a traceback. Pinned in Task 2.
5. **A confirmed date that differs from the rule** (a society moved its night): the event moves to the confirmed date at 100%, and the old predicted date leaves the calendar. Pinned in Task 5.

---

### Task 1: Scaffold the repository

**Files:**
- Create: `pyproject.toml`, `LICENSE` (MIT, copyright line "bonfire-dates contributors"), `.gitignore` (copy albion-tickets' file), `README.md` (one-paragraph stub), `CLAUDE.md`, `.github/workflows/tests.yml` (copy albion-tickets' file; reword the header to say the suite never touches the calendar or the network), `.github/dependabot.yml` (copy albion-tickets'), `src/bonfire_dates/__init__.py`, `src/bonfire_dates/config.py`, `src/bonfire_dates/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `config.TZ = ZoneInfo("Europe/London")`, `config.CALENDAR_NAME = "Bonfire"`, `config.REPO_DIR`, `config.SOCIETIES_FILE = REPO_DIR / "societies.toml"`, `config.CONFIRMED_FILE = REPO_DIR / "confirmed.toml"`, `config.data_dir() -> Path` (env `BONFIRE_DATA_DIR` overrides, else `REPO_DIR / "data"`), `config.MARK = "bonfire-dates:"`, `config.QUESTION_BELOW = 70`; a Click group `cli` with `[project.scripts] bonfire = "bonfire_dates.cli:cli"`.

- [ ] **Step 1:** `git init` in `bonfire-dates`. `git add docs/` (the spec and this plan are already there).
- [ ] **Step 2:** Write `tests/test_cli.py::test_help_lists_commands`. It invokes `cli` with `--help` through `click.testing.CliRunner` and asserts exit code 0 and the text "Sussex bonfire".
- [ ] **Step 3:** Write the files above. `CLAUDE.md` holds the hard rules from Global Constraints, a "Layout" section to fill in as modules land, and the conventions line from albion-tickets.
- [ ] **Step 4:** `uv sync && uv run pytest -q`. Expected: 1 passed.
- [ ] **Step 5:** Commit on `main`: `chore: scaffold bonfire-dates with design and plan`. Then `git switch -c feat/first-version`.

### Task 2: Data model and loader

**Files:**
- Create: `src/bonfire_dates/model.py`, `src/bonfire_dates/load.py`
- Test: `tests/test_load.py`

**Interfaces:**
- Produces (model.py, all frozen dataclasses):
  - `SOURCES = ("verified", "society", "guides", "guide", "wiki")`. This is the trust order, highest first.
  - `Evidence(source: str, url: str | None = None, checked: date | None = None, note: str | None = None)`
  - `Known(date: date, evidence: Evidence)`
  - `Rule(month: int | None = None, day: int | None = None, nth: int | None = None, weekday: str | None = None, anchor: str | None = None, direction: str | None = None, weeks: int = 0, days: int = 0, sunday: str | None = None, guess: bool = False, evidence: Evidence | None = None)`
  - `Society(id: str, name: str, kind: str, status: str, place: str | None, start: time | None, rule: Rule | None, known: tuple[Known, ...], of: str | None, links: dict[str, str], emoji: str | None, confidence: int | None, why: str | None, rate_on_evidence: bool, note: str | None)`
  - `Catalogue(societies: dict[str, Society], badge_confidence: int)`
- Produces (load.py): `load(societies_path: Path, confirmed_path: Path | None) -> Catalogue`, which raises `DataError(problems: list[str])`; and `problems(cat: Catalogue) -> list[str]`, for the checks that need a full catalogue.

**TOML shape** (the design leaves the exact schema to the builder; this plan fixes it):

```toml
[defaults]
badge_confidence = 10

[firle]
name = "Firle"
kind = "night"            # night | badge | other
status = "active"         # active | unknown | gone
place = "Firle, East Sussex"
start = "18:00"           # optional; absent = all-day event
links = { website = "https://…", facebook = "https://…", x = "https://…" }
rule = { anchor = "newick", weeks = -1 }
known = [ { date = 2026-10-24, source = "society", url = "https://…" }, … ]

[firle-badge]
name = "Firle badge night"
kind = "badge"
of = "firle"
rate_on_evidence = true   # otherwise badge nights take defaults.badge_confidence
rule = { anchor = "firle", weekday = "wed", direction = "before" }
```

A rule takes one of three forms:
- `{ month, weekday, nth }`, where `nth = -1` means the last;
- `{ month, day, sunday = "sat-before" }`;
- `{ anchor, weekday?, direction?, weeks?, days? }`.

`anchor` is `"nov5"`, `"remembrance-sunday"` or a society id. `direction` is `before`, `after` or `nearest`, strictly excluding the anchor day itself. Evidence for the rule itself goes in `rule.source`, `rule.url` and `rule.checked`. `confirmed.toml` is a list of `[[confirmed]]` tables with the keys `society`, `date`, `source`, `url` and `checked`. Each one is merged into that society's `known`.

- [ ] **Step 1:** Write the failing tests in `tests/test_load.py`, building small TOML files in `tmp_path`:
  - `test_loads_rule_known_and_links`: a two-society file loads, and `cat.societies["firle"].rule.anchor == "newick"`, `rule.weeks == -1`, `known[0].evidence.source == "verified"` and `links["website"]` are set.
  - `test_confirmed_file_merges_into_known`: a `[[confirmed]]` entry appears in `known` with its `url` and `checked`.
  - `test_syntax_error_is_a_data_error`: broken TOML raises `DataError`, and its message contains the file name and "line".
  - `test_unknown_anchor_unknown_source_and_cycle_all_reported`: a file with `anchor = "nowhere"`, `source = "rumour"` and a two-society cycle raises `DataError` with three problems, each naming its society id. The cycle one names both ids.
  - `test_confirmed_for_unknown_society_is_a_problem`.
- [ ] **Step 2:** `uv run pytest tests/test_load.py -q`. Expected: FAIL (`ModuleNotFoundError`).
- [ ] **Step 3:** Implement `model.py` and `load.py`. Collect every problem before raising, never stopping at the first. Use depth-first search over the anchor edges to find cycles.
- [ ] **Step 4:** Run the tests. Expected: all pass.
- [ ] **Step 5:** Commit: `feat: societies data model and loader`.

### Task 3: Rules engine and seed data

**Files:**
- Create: `src/bonfire_dates/rules.py`, `societies.toml` (all appendix rows and the `unknown` list from the spec, with links where the spec's research found them)
- Test: `tests/test_rules.py`, `tests/test_seed.py`

**Interfaces:**
- Consumes: `Catalogue` and `Rule` (Task 2).
- Produces: `date_for(cat: Catalogue, society_id: str, year: int) -> date | None`. It returns the year's known date if there is one; otherwise the rule's date; otherwise `None`, when there's no rule or the anchor can't be resolved. Also `rule_date(cat, society_id, year) -> date | None`, which uses the rule only and ignores known dates (confidence needs it), and `describe(rule: Rule) -> str`, the rule in words, e.g. "Wednesday before Firle".

- [ ] **Step 1:** Write `tests/test_rules.py` using a small in-memory catalogue:
  - `test_nth_and_last_weekday`: `{month=9, weekday="sat", nth=1}` gives 2027-09-04; `nth=-1` gives 2027-09-25.
  - `test_lewes_sunday_rule`: `{month=11, day=5, sunday="sat-before"}` gives 2027-11-05 and **2028-11-04**.
  - `test_anchor_weekday_direction`: Battle `{anchor="nov5", weekday="sat", direction="after"}` gives 2027-11-06 and 2028-11-11. Newick `{…"before"}` gives 2027-10-30. East Hoathly `{anchor="remembrance-sunday", weekday="sat", direction="before"}` gives 2027-11-13.
  - `test_anchor_on_society_with_weeks_and_days`: Firle (newick, weeks=-1) gives 2027-10-23. Lewes badge (lewes, days=-1) gives 2028-11-03.
  - `test_known_date_wins_for_its_year`: `date_for` returns a known date even when the rule disagrees, but `rule_date` returns the rule's date.
  - `test_no_rule_is_none`.
  - `test_describe` for the Firle badge rule and the Uckfield rule.
- [ ] **Step 2:** Run and see them fail.
- [ ] **Step 3:** Implement `rules.py`. `remembrance-sunday` is the 2nd Sunday of November. `nearest` picks the closer side, and on a tie the earlier date.
- [ ] **Step 4:** Write `societies.toml` from the spec's appendix:
  - Lewes: `place = "Lewes, East Sussex"`, `confidence = 99`, `why = "fixed by tradition"`, and `note` listing the six societies.
  - Nevill: `rule = { anchor = "nov5", weekday = "sat", direction = "before", weeks = -1, guess = true }`.
  - Hawkhurst: no rule.
  - Barcombe: the 3rd-Saturday rule, with a `note` giving the "week after Rye" alternative.
  - Firle and Lewes badge nights: `rate_on_evidence = true`.
  - Buxted: rule evidence `{source="society", note="always the last Saturday of September"}`.
  - Glynde parade: `start = "19:30"`; Glynde membership night: `start = "19:00"`.
  - Everything in the spec's `unknown` list: `status = "unknown"`.
  - Cuckfield: `note = "ticketed fireworks display, not a society night"`.
  - Links: only those already found (Firle, Littlehampton, Hastings, Northiam, South Heighton, Nevill, Buxted, the Glynde Facebook page). The rest are left for research.
- [ ] **Step 5:** Write `tests/test_seed.py::test_2027_dates_match_appendix`. It loads the real `societies.toml` and asserts `date_for` for every active row of the appendix as a parametrised table of `(id, date(2027, m, d))`. Hawkhurst is expected to be `None`. Also add `test_seed_has_no_problems` (`problems(cat) == []`) and `test_seed_is_neutral`, which asserts that the file contains none of `observed`, `went`, `attended`, `/Users/`, `@`.
- [ ] **Step 6:** `uv run pytest -q`. Expected: all pass.
- [ ] **Step 7:** Commit: `feat: rules engine and seed data`.

### Task 4: Confidence and predictions

**Files:**
- Create: `src/bonfire_dates/confidence.py`, `src/bonfire_dates/predict.py`
- Test: `tests/test_confidence.py`, `tests/test_predict.py`

**Interfaces:**
- Consumes: `date_for`, `rule_date` and `describe` (Task 3).
- Produces:
  - `WEIGHTS = {"verified": 1.0, "society": 0.9, "guides": 0.6, "guide": 0.35, "wiki": 0.25}`
  - `rate(cat, society_id, year) -> Rating(percent: int, confirmed: bool, matches: list[Known], contradictions: list[Known], why: str)`
  - `Prediction(key: str, society: Society, day: date, percent: int, confirmed: bool, rating: Rating)`, with properties `title: str`, `notes: str`, `start: datetime`, `end: datetime` and `all_day: bool`
  - `predictions(cat, year) -> list[Prediction]`, active societies only, sorted by day then name

**The formula** (written here because the spec leaves it to the builder):
1. If the year has a known date: 100, confirmed.
2. If the entry has a `confidence` override: that value.
3. If it's a badge without `rate_on_evidence`: `cat.badge_confidence`.
4. Otherwise, s = the sum of `WEIGHTS` over the evidence that matches. That's every known date from another year where `rule_date` equals the known date, plus the rule's own evidence. The percent is `min(92, round(25 + 25 * s))`.
5. If any `verified` or `society` known date contradicts the rule, cap at 60. If the rule is a `guess`, cap at 35.
6. Clamp to 1–99.

- [ ] **Step 1:** Write `tests/test_confidence.py` for 2027, giving societies history generated from their own rules (never typed-in dates):
  - Three verified years that the rule fits give 92; two give 75.
  - A trusted known date that the rule misses caps the rating at 60 and is listed as a contradiction.
  - Badge nights not rated on evidence are 10.
  - Lewes is 99.
  - Nevill (a guessed rule) is ≤ 35.
  - Also `test_known_date_makes_it_confirmed_100`.
- [ ] **Step 2:** Write `tests/test_predict.py`:
  - `test_title_marks_uncertain`: Ninfield's title is `"🔥 Ninfield?"` and Uckfield's is `"🔥 Uckfield"`. The `?` appears below `config.QUESTION_BELOW`.
  - `test_emoji_by_kind`: badge → 🦡, the fancy dress → 🎭, the memorial parade → 🕯️. This comes from an `emoji` key in the data, defaulting to 🔥 for a night and 🦡 for a badge.
  - `test_notes_start_with_confidence_then_rule_then_evidence`: the notes' first line is `"Confidence 92%"`. They contain `describe(rule)` and each matching date with its source, and end with `"Predicted, not published."` until confirmed.
  - `test_timed_vs_all_day`: the Glynde parade runs 19:30–22:30 Europe/London; an entry with no `start` is all-day.
  - `test_keys`: `"firle:2027"`.
  - `test_unknown_and_ruleless_societies_have_no_prediction`.
- [ ] **Step 3:** Run and see them fail. Implement. Run again. Expected: all pass.
- [ ] **Step 4:** Commit: `feat: confidence percentages and predictions`.

### Task 5: Calendar bridge, local state and sync

**Files:**
- Create: `src/bonfire_dates/calendar.js` (copied from albion-tickets, with `MARK = 'bonfire-dates:'` and all-day support), `src/bonfire_dates/calendar_app.py` (copied and trimmed: `Change`, `Event`, `Calendar`, `FakeCalendar`, `MacCalendar`, `CalendarError`; `_payload` adds `"allDay"`; alarms always `[]`), `src/bonfire_dates/store.py`, `src/bonfire_dates/sync.py`
- Modify: `src/bonfire_dates/cli.py` (the `sync` command)
- Test: `tests/test_calendar.py`, `tests/test_store.py`, `tests/test_sync.py`

**Interfaces:**
- Consumes: `Prediction` and `predictions` (Task 4).
- Produces:
  - `store.State(events: dict[str, dict])`, where each value is `{"uid": str, "day": "YYYY-MM-DD"}`; `store.load(path) -> State`; `store.save(state, path, today)`, which writes atomically and keeps one dated backup per day in `data/backups/`, the last 30.
  - `sync.plan(cat, state, today) -> SyncPlan(upserts: list[Prediction], removals: list[str])`
  - `sync.run(cat, cal: Calendar, state_path: Path, today: date, dry_run: bool) -> SyncResult(written: int, removed: int, failed: list[tuple[str, str]])`

**calendar.js all-day:** when `req.allDay` is set, `ev.allDay = true` and the start and end are local midnights, with the end the following midnight. Otherwise behaviour is as in albion-tickets. Compare with `Number(…)` as in albion-tickets' CLAUDE.md.

**Sync rules:**
- The horizon is the current year (days ≥ today) and the next year.
- Never write or remove an event dated before today.
- A key in the state but no longer predicted, dated today or later, is removed.
- A prediction whose day changed is upserted with its stored uid, so the event moves.
- Only successes are recorded; failures stay as they were and retry on the next run.
- `--dry-run` prints the plan and changes nothing.

- [ ] **Step 1:** Write the failing tests:
  - `tests/test_calendar.py::test_payload_all_day_and_no_alarms`, and `test_mac_calendar_with_stand_in_command`, which uses a stand-in script echoing `{"ok":true,"uid":"u1"}` lines as albion's tests do.
  - `tests/test_store.py`: `test_round_trip`, `test_backup_kept_once_per_day_last_30`.
  - `tests/test_sync.py`, using `FakeCalendar` and seed data with `today = date(2026, 11, 15)`:
    - `test_first_sync_writes_rest_of_2026_and_all_2027`: Barcombe 2026-11-21 is written; Firle 2026 is not (past).
    - `test_second_sync_is_idempotent`: zero upserts.
    - `test_confirmed_date_moves_event`: add a known 2027-10-30 for Firle; the same uid now holds 2027-10-30, the title has no `?`, and the notes say 100%.
    - `test_society_set_unknown_removes_future_event`.
    - `test_past_events_never_touched`.
    - `test_failed_write_is_not_recorded`: the fake returns `CalendarError` for one key, so the state lacks it and the next run retries it.
    - `test_missing_calendar_exits_1_state_unchanged`: through the CLI with `check_ready` returning the albion message.
- [ ] **Step 2:** Run and see them fail. Implement. Run again. Expected: all pass.
- [ ] **Step 3:** Add `bonfire sync [--dry-run]` to `cli.py`. It prints one summary line, e.g. "Bonfire calendar: 38 written, 0 removed", with any failures listed in yellow beneath.
- [ ] **Step 4:** Commit: `feat: Bonfire calendar sync with all-day events`.

### Task 6: Commands for reading and research

**Files:**
- Create: `src/bonfire_dates/display.py` (adapted from albion-tickets: `table`, `title`, `dim`, plus `percent_style(p) -> dict`, which is green at ≥ 85, default at ≥ 70, yellow at ≥ 35 and red below), `src/bonfire_dates/research.py`
- Modify: `src/bonfire_dates/cli.py`
- Test: `tests/test_cli.py`, `tests/test_research.py`

**Interfaces:**
- Consumes: `load`, `problems`, `predictions`, `rate` and `describe`.
- Produces:
  - `research.append_confirmed(path, society_id, day, source, url, checked) -> None`, which appends a `[[confirmed]]` block as text, quoting strings with TOML escaping.
  - `research.file_evidence(data_dir, society_id, src: Path, today) -> Path`, which copies the file to `data/evidence/<id>/<YYYY-MM-DD>-<name>`, adding `-2`, `-3` and so on rather than overwrite.
  - `research.resolve_id(cat, text) -> str`, which raises `click.BadParameter` with up to 3 `difflib` suggestions.
  - `research.todo(cat, year, today) -> list[Prediction]`, the unconfirmed predictions dated today or later.

**Commands:**

| Command | Output |
|---|---|
| `bonfire predict [YEAR] [-v] [--json]` | A table per month (yellow bold month heading): Date (`Sat 23 Oct`), Event, Confidence (styled with `percent_style`). `-v` adds Rule and Evidence columns. `--json` is a plain list. YEAR defaults to the next season that hasn't ended. |
| `bonfire list` | Every society with Status, Rule (`describe`) and Evidence years, with `unknown` and `gone` dimmed |
| `bonfire check` | "No problems" in green, or each problem in yellow and exit code 1 |
| `bonfire confirm ID DATE [--source verified] [--url U] [--checked D]` | Appends to `confirmed.toml` and prints the event's new state |
| `bonfire todo [YEAR]` | The research list: Date, Event, Confidence, Last checked, then the links indented and dimmed under each |
| `bonfire sources ID` | Links, rule evidence, each known date with source, url and checked, and local evidence files |
| `bonfire evidence ID FILE` | Files the evidence and prints where it went |

- [ ] **Step 1:** Write the failing tests:
  - `test_predict_2027_table_has_months_and_percentages`: the plain output contains "October", "Firle" and "92%".
  - `test_predict_json_is_plain`: no `\x1b`; parses as JSON.
  - `test_confirm_unknown_id_suggests_and_changes_nothing`: `firl` → exit code 2, "firle" in the output, and the `confirmed.toml` bytes unchanged.
  - `test_confirm_appends_and_reloads`: the round trip through `load` gives 100% for that year.
  - `test_evidence_never_overwrites`.
  - `test_todo_lists_only_unconfirmed_future_with_links`.
  - `test_check_reports_problems_exit_1`.
  - `test_list_shows_unknown_dimmed_when_tty`. Force styling with `color=True` in `CliRunner.invoke`, then check for the dim escape.
- [ ] **Step 2:** Run and see them fail. Implement. Run again. Expected: all pass.
- [ ] **Step 3:** Commit: `feat: predict, list, check, confirm, todo, sources and evidence`.

### Task 7: Documentation and the user's first look

**Files:**
- Modify: `README.md` (what it is, setup: create the "Bonfire" calendar in Calendar.app under iCloud, `uv sync`, `bonfire predict`, `bonfire sync --dry-run`, `bonfire sync`; a command table; how to add a society or rule; the research workflow with `todo`, `confirm` and `evidence`; why there's no automated fetching; MIT), `CLAUDE.md` (the Layout section listing each module's job in one line)

- [ ] **Step 1:** Write the README and CLAUDE.md.
- [ ] **Step 2:** `uv run pytest -q` passes. `grep -rnE "/Users/|@gmail|observed|attend" --include='*' . | grep -v '^./.venv'` returns nothing outside the tests' own forbidden-word list. As a control, first run the same grep for a word known to be present (e.g. `Firle`) to prove it works.
- [ ] **Step 3:** Run `uv run bonfire predict 2027 -v` and `uv run bonfire sync --dry-run`. Paste both outputs for the user, with each 2027 percentage beside the spec appendix's word rating, so they can override any. Do **not** run a real `sync`: the user does that.
- [ ] **Step 4:** Commit: `docs: README and project notes`. Leave the branch unmerged for the user's review.
