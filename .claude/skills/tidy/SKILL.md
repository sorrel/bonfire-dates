---
name: tidy
description: Use when the user says "tidy", "/tidy" or asks to search for new bonfire dates and sources and then update the Bonfire calendar in one go. Searches the web by hand for each society's current pages and dates, records them under the README's rules, checks the data, syncs the calendar, then commits and opens a PR.
---

# Tidy: search for sources, then sync

One pass that does the README's "Looking for sources" routine and then
`bonfire sync`. The search is done here by the assistant, by hand, with web
search and page reads. The tool itself never fetches anything, and nothing in
this skill may be turned into code that does (CLAUDE.md: no automated
fetching).

Arguments: society IDs to search (e.g. `/tidy firle newick`). With none,
search every entry whose status is `active` or `unknown`, oldest `searched`
first (never searched counts as oldest). Skip `gone` and `visiting` entries
unless named; `visiting` ones have no dates to find.

## 1. Start

- From `main`, pull, then branch: `data/tidy-YYYY-MM-DD` (today's date).
- Run `uv run bonfire todo` and `uv run bonfire list` to see what is still
  predicted, how sure each is, and when it was last checked.
- Tell the user which societies you will search, in a short line.

## 2. Search each society

For each one, run `uv run bonfire sources <id>` first, so you know its links,
rule and the dates already held. Then search for its own website and pages,
and its dates for the season being predicted (and the current year, if Lewes
night hasn't passed). Read the pages themselves; never record a date from a
search snippet.

Record by the README's rules, strictly:

- **A link** goes in `links` only once you have seen it live and it is the
  society's own. Check addresses quoted by guides or old news first.
- **A date** is recorded at its real trust level, with
  `uv run bonfire confirm <id> <date> --source <level> --url <url>`:
  `society` only from the society's own site, page or poster; `guides` when two
  independent guides agree; otherwise `guide`. `wiki` for Wikipedia.
  **Never `verified`:** that is for dates the user knows first-hand.
- **Make sure the event is the society's own.** Councils, schools and venues
  run fireworks nights in the same towns (often on 5 November), and guides and
  news stories mix them up with the society's procession. A date for an event
  run by someone else is never recorded against the society. If you can't tell
  who runs it, list it for the user to judge.
- **A disagreement** with a date already held is not recorded. List it for the
  user to judge (postponement, cancellation, typo).
- **A rule that looks wrong** (a new date it misses) is reported, not changed.
- **A status change** (an `unknown` or `gone` society seen active again, or an
  active one apparently ended) is reported, not changed, unless the evidence is
  the society's own announcement; then say what you changed.
- Set `searched = <today>` on every entry you searched, found something or not.
- `confirm` refuses a badge night that isn't before its society's night. Treat
  that as a disagreement to report, not something to work around.

Keep it neutral: no search, note or commit message may say which societies
the user belongs to or attends. Don't save evidence files unless asked
(`bonfire evidence` keeps them in gitignored `data/evidence/`).

## 3. Check and sync

1. `uv run bonfire check`: no problems; note any rules that now miss a date.
2. `uv run pytest -q`: all pass. If `tests/test_seed.py` fails because the data
   changed, update its pinned dates only to match the new evidence.
3. `uv run bonfire sync --dry-run`, then show the user what it will change.
4. `uv run bonfire sync`. Report the restored, de-duplicated and changed
   events. If it couldn't read the calendar back, say so.

## 4. Finish

- Commit on the branch (message starts `data:`, saying what was found, by
  society, without saying who attends what) and open a PR. If nothing changed
  but `searched` dates, still commit those.
- End with a short summary for the user, laid out as tables:
  - **Found:** society, what (date / link), source level, URL.
  - **For you to judge:** disagreements, possible rule changes, status changes.
  - **Calendar:** what sync changed.
  - The PR link.
