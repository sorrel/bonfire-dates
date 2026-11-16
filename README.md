# 🔥 bonfire-dates

**Sussex bonfire society nights, predicted a season ahead, in their own calendar.**

From September to November, Sussex bonfire societies hold torchlit processions,
most on a night fixed by an unwritten rule: "the first Saturday of September",
"the Saturday before the 5th". Few publish their dates early. This tool keeps
each society's rule and the dates seen so far, predicts the coming season,
rates each prediction as a percentage, and puts the lot in a calendar of its
own. When a date is published, record it and the event becomes certain.

It never fetches anything. Much of the real news is on Facebook and X, which
can't be read automatically, and websites are often wrong, so research is done
by hand and every date is recorded with its source.

## Setup

1. In Calendar.app, create a calendar named **Bonfire** under iCloud.
2. `uv sync`
3. `uv run bonfire predict 2027` to see the season.
4. `uv run bonfire sync --dry-run`, then `uv run bonfire sync`. Allow **full
   calendar access** when macOS asks. Only the Bonfire calendar is ever changed.

Events with a known start time are timed; the rest are all-day. Titles are
plain; each event's notes start with how sure the date is ("Confidence 85%"),
then the rule and the evidence behind it.

## Commands

| Command | What it does |
|---|---|
| `bonfire predict [YEARS] [-v] [--json]` | The season month by month, with how sure each date is. YEARS is a year (`2028`) or a span (`2027-2029`) |
| `bonfire sync [--dry-run]` | Bring the Bonfire calendar in line (the next 18 months; after Lewes night, this year shows only known dates). Reads the calendar back first: restores an event deleted by hand, removes duplicates, and lists events it didn't make without touching them. Lists each event added, restored, moved (with its old date), updated (with its old percentage) or removed, then a tally, what the calendar holds and the next event. Exits 1 if any write failed; those retry next time |
| `bonfire todo [YEARS]` | What's still only predicted, with each society's links; `2027-2029` looks a few seasons ahead |
| `bonfire confirm ID DATE [--source …] [--url …]` | Record a date once it's known |
| `bonfire evidence ID FILE` | Keep a poster or screenshot locally (never published) |
| `bonfire sources ID` | The links and evidence behind a society's dates |
| `bonfire list` | Every society and event: its ID (what other commands take), rule and known years |
| `bonfire check` | Check the data files |

## Keeping it up to date

1. `bonfire todo 2027` lists the events still to confirm and where to look.
2. When a date turns up, `bonfire confirm firle 2027-10-23 --source society --url …`.
3. `bonfire evidence firle poster.jpg` if there's a poster worth keeping.
4. `bonfire sync`.

Sources, most trusted first: `verified` (known to be right), `society` (its own
site, poster or page), `guides` (two guides that agree), `guide`, `wiki`.

Dates you know first-hand (`--source verified`, the default) are **private**:
they go into `data/known.toml`, which is never committed, and are merged in
when the data loads. Only dates with a public source go into the public
`confirmed.toml`. So the repository never shows whose season it reflects, and
your own copy still rates your well-known societies higher.

## Keeping the calendar fresh in the background

`tools/install-refresh.sh` installs a launchd agent that runs
`tools/refresh.sh` every morning at 07:30 (or on wake, if the Mac was asleep):
`bonfire check`, then `bonfire sync`. It fetches nothing; new dates still come
from research by hand. It keeps the calendar right as time passes: the 18-month
horizon rolls on, this year drops to known dates after Lewes night, events
deleted by hand come back and failed writes retry. Data problems leave the
calendar alone. The log is `data/refresh.log`; `tools/install-refresh.sh
--remove` takes it out.

## Looking for sources

Websites move and lapse (one society's old domain now belongs to someone
else), so once a season, and whenever there's reason to, search for each
society's current pages, by hand or with an assistant. The tool itself still
fetches nothing. The rules:

- A link is added only once it has been seen live and is the society's own.
  An address quoted by a guide or an old news story is checked first.
- A date read online is recorded at its real trust level: `society` only
  from the society's own site or poster, otherwise `guide` at best.
- Make sure the event is the society's own. Councils, schools and venues
  run fireworks nights in the same towns, often on 5 November, and listings
  mix them up with the society's procession. Leave out anything run by
  someone else. `confirm` refuses a 5 November date from a public source for
  a society whose rule puts its night elsewhere; `--own-event` overrides it
  once you've checked.
- A source that disagrees with a date already held is not recorded; it is
  listed for a person to judge (a postponement, a cancellation, a typo).
- Each society searched gets `searched = YYYY-MM-DD` in `societies.toml`.
  `bonfire sources` shows it, and `todo`'s Checked column counts it, so a
  society not looked at for a while stands out.

In Claude Code, `/tidy` does the whole round in one go: it searches for each
society's sources by these rules, records what it finds, checks the data,
syncs the calendar and opens a PR (`.claude/skills/tidy/SKILL.md`). Name
societies to search just those, as in `/tidy firle newick`.

## How confidence works

A confirmed date is 100%. Otherwise the rule is checked against the society's
known dates from other years: each one it reproduces adds weight by source
(verified 1.0, society 0.9, guides 0.6, guide 0.35, wiki 0.25), and the
percentage is 25 + 25 × weight, up to 92%. A rule that misses a verified or
society date is capped at 60%, and a guessed rule at 35%. Badge nights are 10%
unless marked to be rated on their evidence. Lewes is set by hand at 100% (fixed by tradition) and Lindfield at 95%; a
hand-set 100% has no ✓, which marks a date published or known for that year.

## Adding a society or a rule

Edit `societies.toml`; its header explains the rule forms. Then run
`bonfire check`. Rules can be the nth weekday of a month, a fixed day, or
relative to an anchor: 5 November, Remembrance Sunday, or another society
(Firle is "a week before Newick").

Local state (private dates, event IDs, evidence files, backups) lives in
`data/`, which is never committed.

MIT licence.
