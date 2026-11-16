# CLAUDE.md

Predicted Sussex bonfire society nights (and badge nights and linked events),
each with a confidence percentage, in a dedicated iCloud calendar ("Bonfire").
Design: `docs/superpowers/specs/2026-11-15-bonfire-dates-design.md`.

## Hard rules

- **Only the "Bonfire" calendar is ever changed.** EventKit's access reaches
  every calendar, so `calendar.js` refuses an event ID found elsewhere.
- **Neutral about the user.** No tracked file may show which societies the
  user belongs to or which events they attend. Date sources say how a date is
  known (`verified`, `society`, `guides`, `guide`, `wiki`), never by whom.
- **Going is private.** Events the user is going to live only in gitignored
  `data/going.toml` (`bonfire going`), keyed by society and year; a marked
  event is timed with the user's hours instead of all-day.
- **First-hand dates are private.** `verified` dates live only in gitignored
  `data/known.toml` (merged by `load`); `societies.toml` and `confirmed.toml`
  hold only dates with a public source. `test_seed_is_neutral` enforces it.
  Tests generate any history they need from the rules (`tests/helpers.py`).
- No personal information in any tracked file: no names, addresses, emails,
  `/Users/...` paths, or calendar names other than "Bonfire". Evidence files
  (posters, screenshots) stay in gitignored `data/evidence/`.
- **No automated fetching**, of websites, Facebook or X. Research is done by
  hand and recorded with its source.
- A failed calendar write never loses an event: only successes are recorded,
  and failures retry on the next sync. Past events are never touched.
- Events without the `bonfire-dates:` URL mark were made by hand: sync lists
  them and never changes them. Sync reads the calendar back (`reconcile`)
  before planning; if the read fails it trusts `state.json` and says so.
- Tests never touch the network or the real calendar (`FakeCalendar`, or
  `MacCalendar` with a stand-in command). Check behaviour with `--dry-run`.

## Conventions

uv, Python ≥ 3.15 (latest only), src layout, Click is the only runtime
dependency, British English, feature branches only, designed terminal output.

## Layout

`societies.toml` + `confirmed.toml` → `load` (`Catalogue`, all problems
collected) → `rules` (`date_for`, `rule_date`, `describe`) → `confidence`
(`rate`: percentages, formula in its docstring) → `predict` (`Prediction`:
title, notes, all-day or timed) → `sync` (state hash per event, horizon the next
18 months, but only known dates for this year once Lewes night has passed;
past events untouched) → `calendar_app` + `calendar.js`
(EventKit, copied from albion-tickets, plus all-day). `research` handles
`confirm` (appends text to `confirmed.toml`), local evidence and `todo`.
`cli.py` holds only commands; `display.py` the shared table helpers.
`/tidy` (`.claude/skills/tidy/`) is the assistant's routine: search for sources
by hand under the README's rules, then sync. It is never code that fetches.
`tools/refresh.sh` (installed as a launchd agent by `tools/install-refresh.sh`,
which writes the plist outside the repo) runs `check` then `sync` daily.

- A rule's anchor may be another society: if Newick's date is known, Firle
  follows it. Anchors must not form cycles (`load` refuses them).
- A badge night always comes before its society's night in the same year,
  though not always just before. Known dates that break this are a load
  problem and `confirm` refuses them; a predicted date that breaks it is left
  out (`rules.out_of_order`: a known date never gives way; if both are
  predicted, the badge night's does).
- A `visiting` society has no home location, procession or event of its
  own: listed, never predicted, and it may not have a rule or dates.
- Each event's URL is `bonfire-dates:<society>:<year>`, so a write whose reply
  was lost is found and updated, never duplicated.
- `tests/test_seed.py` pins every 2027 date from the design's appendix and
  checks the data stays neutral. Change it only with the data.
