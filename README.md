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
| `bonfire predict [YEAR] [-v] [--json]` | The season month by month, with how sure each date is |
| `bonfire sync [--dry-run]` | Bring the Bonfire calendar in line (the rest of this year and next; after Lewes night, this year shows only known dates): lists each event added, moved (with its old date), updated (with its old percentage) or removed, then a tally, what the calendar holds and the next event. Exits 1 if any write failed; those retry next time |
| `bonfire todo [YEAR]` | What's still only predicted, with each society's links |
| `bonfire confirm ID DATE [--source …] [--url …]` | Record a date once it's known |
| `bonfire evidence ID FILE` | Keep a poster or screenshot locally (never published) |
| `bonfire sources ID` | The links and evidence behind a society's dates |
| `bonfire list` | Every society and event, with its rule |
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

## How confidence works

A confirmed date is 100%. Otherwise the rule is checked against the society's
known dates from other years: each one it reproduces adds weight by source
(verified 1.0, society 0.9, guides 0.6, guide 0.35, wiki 0.25), and the
percentage is 25 + 25 × weight, up to 92%. A rule that misses a verified or
society date is capped at 60%, and a guessed rule at 35%. Badge nights are 10%
unless marked to be rated on their evidence. Lewes is set by hand at 99%.

## Adding a society or a rule

Edit `societies.toml`; its header explains the rule forms. Then run
`bonfire check`. Rules can be the nth weekday of a month, a fixed day, or
relative to an anchor: 5 November, Remembrance Sunday, or another society
(Firle is "a week before Newick").

Local state (private dates, event IDs, evidence files, backups) lives in
`data/`, which is never committed.

MIT licence.
