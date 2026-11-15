# bonfire-dates: design

Date: 15 November 2026. Status: approved 15 November 2026.

## Intent

Sussex bonfire societies hold their torchlit processions from early September
to late November. Most societies keep to an unwritten rule ("the first Saturday
of September", "the Saturday before the 5th"), but few publish dates early and
some publish none at all. `bonfire-dates` predicts each society's night for
the coming season and puts it, with a confidence rating, into a dedicated
iCloud calendar ("Bonfire"). When a date is published or verified, recording
it lifts the event to "confirmed".

It is a sister project to `albion-tickets` (same workspace, same conventions)
and is published as a public GitHub repository: well designed, secure and
free of personal information.

## Goals

- A season at a glance, a year ahead: every active society's night, plus
  linked events (badge nights, the Lewes fancy dress, the Glynde memorial
  parade), predicted from rules.
- An honest confidence rating on every event, derived from evidence rather
  than asserted.
- One plain data file that a person can read and correct: societies, rules,
  known past dates and where each date came from.
- Its own calendar, kept in step by `bonfire sync`, and never touching any
  other calendar.
- Readable, designed terminal output (workspace convention).

## Non-goals (for this first version)

- **No automated fetching.** Websites are often wrong: Wikipedia's rules for
  Mayfield and Barcombe contradict verified dates, and one source declared the
  Hawkhurst Gang dissolved in 2024, though it held a night in 2026. Much of the
  real news is on Facebook and X, which block automated access and forbid
  scraping; an automated visit could get the user's own accounts flagged.
  Research is done by hand, or by Claude in a session, and every finding is
  recorded with its source (see "Sources and research").
- No reading of any other calendar. Past dates are entered by hand.
- No tracking of same-day weather moves. In 2026 Firle and Littlehampton moved
  from the 24th to the 25th, decided on the day. The tool predicts the planned
  night only.
- No alarms on events (it's a planning calendar, not a reminder service), and
  no launchd schedule: predictions change only when the data changes, so
  `sync` is run by hand after an edit or a `confirm`.
- No attendance tracking ("going" or "went"). The calendar shows what's on,
  for every society alike.

## Anti-goals (failure even if it works)

- Personal data in the repository: names, addresses, calendar names other than
  "Bonfire", or `/Users/...` paths.
- Anything that reveals which societies the user belongs to or which events
  they attend. The public record is neutral on both: every society is treated
  alike, and sources say how a date is known (`verified`), never by whom.
- Changing or deleting any event outside the Bonfire calendar.
- False confidence: a guess shown with the same weight as a near-certainty.
- Inventing events. A society or badge night with no evidence gets no event.

## Approaches considered

| | Approach | Trade-off |
|---|---|---|
| **A (chosen)** | Hand-written rules per society in a data file, a confidence score from how well each rule matches recorded past dates, and a sync to a dedicated calendar using albion-tickets' EventKit bridge | Rules are readable and correctable. Confidence has a basis. The bridge is proven (no duplicates, refuses other calendars). |
| B | Infer each society's rule from its past dates automatically | With one to three years per society it can't tell "last Saturday of October" from "a week before Newick". It would have mis-predicted Firle. |
| C | Generate a one-off `.ics` file to import | Quickest, but nothing updates when dates are confirmed, and it must be redone each year. |

A was chosen.

## Decisions taken

- **Lewes** means seven societies: Cliffe, Borough, Commercial Square,
  Southover, South Street, Waterloo and Nevill. The first six hold one shared
  night (one calendar event) on 5 November, or on the Saturday before when the
  5th is a Sunday. Nevill (the juvenile society) holds its own, earlier night.
- **Badge nights are included.** They are predicted from rules, never looked up
  ahead ("no-one is that organised"). The Lewes badge night is the evening
  before the Lewes procession. Badge nights with no evidence get no event.
- **The Lewes fancy dress** (Lewes Town Hall) and the **Glynde, Beddingham &
  Firle Memorial Parade**, with its membership night, are included.
- **Source trust**, highest first: `verified` (known to be right) > `society`
  (the society's own site, poster or page) > `guides` (two independent guides
  that agree) > `guide` (a single guide) > `wiki` (Wikipedia).
- **Hawkhurst Gang** is active (it held a night on Fri 6 Nov 2026). **Cuckfield** is
  a ticketed fireworks display, not a society night: listed as `unknown`, so it
  has no event.
- Battle and East Hoathly & Halland were both on Sat 7 Nov 2026. Their rules
  diverge in 2027: Battle is the first Saturday
  after the 5th (6 Nov), and East Hoathly the nearest Saturday to Remembrance
  Sunday, which is always the day before (13 Nov).
- Confidence is a percentage. Badge nights default to 10%, except Lewes and Firle.

## How it works

### Data: `societies.toml` (tracked, public facts only)

One entry per society or event. An illustrative shape only; the builder
designs the exact schema:

```toml
[firle]
name = "Firle"
kind = "night"                     # night | badge | other
status = "active"                  # active | unknown | gone
place = "Firle"                    # for the calendar location / map pin
start = "18:00"                    # optional; all-day event if absent
rule = { anchor = "newick", weeks = -1 }
known = [
  { date = 2026-10-24, source = "society", url = "https://…", checked = 2026-11-15 },
]

[firle-badge]
name = "Firle badge night"
kind = "badge"
of = "firle"
rule = { anchor = "firle", weekday = "wed", direction = "before" }
```

The rule language must express every pattern in the seed data (appendix):

- the nth (or last) weekday of a month;
- a fixed day of a month, with a Sunday adjustment (Lewes: 5 Nov, or the
  Saturday before when that's a Sunday);
- the nearest weekday before or after a date or a named anchor, optionally
  plus or minus whole weeks;
- named anchors: `nov5` (the Lewes date), `remembrance-sunday` (the second
  Sunday of November), and any other society's id (Firle → Newick, Rye →
  Battle, Barcombe → Rye, badge nights → their own night);
- no rule at all (`rule` absent): the society appears in `bonfire list` but
  gets a calendar event only for a confirmed date.

Anchors must not form cycles. Loading fails loudly, naming the cycle.

### Sources and research

Research needs much more searching and source-keeping than albion-tickets, so
sources are first-class:

- **Links per society** in `societies.toml`: `website`, `facebook`, `x`
  (any may be absent). These are public pages, so they are fine to publish.
- **Every known date carries its evidence:** `source` (trust level), `url`
  (where it was found, if online) and `checked` (the day it was checked). For
  example: `{ date = 2026-11-13, source = "society", url = "https://www.facebook.com/…", checked = 2026-11-15 }`.
- **First-hand (`verified`) dates are private.** They live in gitignored
  `data/known.toml` and are merged on load, so the public data shows only dates
  with a public source, and nothing in the repo maps the user's season.
- **Rules can carry evidence too**, such as Buxted's "always the last Saturday
  of September", with its `url` and `checked`.
- **Local evidence files** (`data/evidence/<society>/<date>-<name>.<ext>`,
  gitignored): screenshots, posters and saved pages. They are kept locally
  because they often carry personal details (contact emails, faces, names).
  `bonfire evidence <society> <file>` copies a file in under that naming.
- **`bonfire todo [YEAR]`:** the season's events that are still only predicted,
  soonest first, each with its society's links and the date of its last check.
  It's the starting point for a research session.
- **`bonfire sources <society>`:** links, rule evidence and each date's
  evidence (online and local).
- `bonfire confirm` takes `--url` and `--checked` (default: today).

### Confidence

Confidence is a **percentage**, computed per event per year:

- **100%, confirmed:** the year has a known date. It is used as-is and wins
  over the rule.
- **Set by hand:** a date fixed by tradition carries its own rating: Lewes
  100% (no ✓, as nothing has confirmed the year), Lindfield 95%.
- **Otherwise, 1–99%:** from how many recorded years the rule reproduces,
  weighted by source trust. As a guide: a rule matching three
  `verified` years ~90%; two trusted years ~75–85%; one trusted year or two
  guides ~50–60%; a single guide, Wikipedia alone, or a rule marked as a guess
  ~20–35%. A rule that contradicts any trusted known date is capped (~60%).
- **Badge nights default to 10%** (few are fixed that far ahead), except Lewes and Firle, which are rated from their evidence like any
  other event. The default lives in the data, not the code, so another
  society's badge night can be raised once it proves regular.
- An optional `confidence = NN` in the data overrides the computed value, with
  a `why` string.
- `bonfire predict` shows each event's percentage and, with `-v`, the evidence
  behind it.

The formula decides; the appendix's word ratings are only a first impression.
The tests pin the computed percentages. Before the first real sync, the builder
shows each 2027 percentage beside the appendix rating so the user can override
any that look wrong (with `confidence = NN` and a `why`).

### Calendar

- `calendar.js` and `calendar_app.py` are copied from albion-tickets and
  trimmed, not imported across repos. They keep: one batch per run; the event
  URL carrying `bonfire-dates:<key>` so a lost reply never duplicates; and a
  refusal of any event ID found in another calendar.
- The calendar is named "Bonfire" (`CALENDAR_NAME` in `config.py`). The user
  creates it in Calendar.app under iCloud, as for albion-tickets.
- Event key: `<society-id>:<year>`.
- Titles: `🔥 Firle` for nights, `🦡 Firle badge night` for badge nights, and a
  fitting emoji for other events (🎭 fancy dress, 🕯️ memorial parade). Titles stay
  plain whatever the rating (the user's call: the percentage already says how
  sure); it goes at the top of the notes ("Confidence 85%").
- The location is the place, pinned by Maps when written (as albion-tickets
  does for non-league grounds).
- Notes: confidence, the rule in words, the evidence, and "predicted, not
  published" until confirmed.
- **Horizon:** `sync` covers the rest of this year and all of next. Once this
  year's Lewes night has passed, the season counts as decided: this year keeps
  only known dates, and predictions are for next year (`prediction_year`). It
  never edits or removes past events.
- When a society's prediction changes, its event moves. When a society leaves
  the active list or loses its rule, its future events are removed.

### Commands (Click)

| Command | What it does |
|---|---|
| `bonfire predict [YEAR] [-v]` | The season as a table grouped by month: date, event, confidence, and with `-v` the rule and evidence |
| `bonfire sync [--dry-run]` | Bring the Bonfire calendar in line with the predictions |
| `bonfire confirm <society> <date> [--source …]` | Record a date (default source `verified`) |
| `bonfire list` | Every society: status, rule in words, years of evidence |
| `bonfire check` | Validate the data file: unknown anchors, cycles, rules that contradict trusted dates |
| `bonfire todo [YEAR]` | Events still only predicted, with links and last-checked dates |
| `bonfire sources <society>` | Links and the evidence behind each date and rule |
| `bonfire evidence <society> <file>` | File a screenshot, poster or saved page locally (never published) |

`confirm` writes to the tracked `societies.toml`, since the dates are public
facts. Its write must keep the file's comments and layout, or else it appends to
a separate tracked `confirmed.toml` that is merged on load. That choice is
left to the builder.

### Local state (`data/`, gitignored)

The event IDs the calendar returned, keyed by event key; the local evidence
files; and a daily backup of both (as albion-tickets does).

## Constraints and conventions

- Workspace `CLAUDE.md` rules: uv, Python ≥ 3.15, src layout
  (`src/bonfire_dates/`), Click the only runtime dependency (`tomllib` is
  standard library; a TOML writer, if needed, must be justified or avoided),
  British English, feature branches, designed terminal output (measure plain,
  style after; `--json` and piped output stay plain).
- Tests never touch the real calendar (`FakeCalendar`, or `MacCalendar` with a
  stand-in command). Check behaviour with `--dry-run`.
- Public-repo baseline: MIT licence, the shared `tests.yml` copied from
  albion-tickets, Dependabot, CodeQL, and the shared rulesets (as
  albion-tickets: GitGuardian and pytest required; not on Aikido). Commits are
  signed as the user.
- No personal information in any tracked file, specs and plans included.
- **Publishing comes last.** Build in a local git repo; create the public
  GitHub repo and apply the rulesets only after the user has reviewed the
  working tool and the full history.

## Left to the builder

The exact TOML schema and rule syntax, module layout, the confidence formula
(within the guide above), table styling, whether `confirm` edits in place or
uses a side file, and default start times.

## Appendix: seed data (first-impression 2027 predictions)

Known past dates are kept in the data, not here: public ones in `societies.toml`
with their sources, first-hand ones privately in the user's `data/known.toml`.

| 2027 | Event | Rule | Rating |
|---|---|---|---|
| Sat 21 Aug | 🦡 Chiddingly badge night (Gun Brewery) | 3rd Sat Aug | 10% (badge default) |
| Sat 4 Sep | 🔥 Uckfield | 1st Sat Sep | high |
| Sat 11 Sep | 🔥 Crowborough | 2nd Sat Sep | high |
| Sat 11 Sep | 🔥 Fletching | 2nd Sat Sep? | low |
| Sat 18 Sep | 🔥 Mayfield | 3rd Sat Sep | high |
| Sat 25 Sep | 🔥 Buxted | last Sat Sep | high |
| Sat 25 Sep | 🔥 Burgess Hill | last Sat Sep | high |
| Sat 2 Oct | 🔥 Eastbourne | 1st Sat Oct | high |
| Sat 2 Oct | 🔥 Northiam | 1st Sat Oct? | medium |
| Sat 2 Oct | 🔥 Rotherfield & Mark Cross | 1st Sat Oct? | low |
| Fri 8 Oct | 🎭 Lewes fancy dress (Lewes Town Hall) | 2nd Fri Oct | high |
| Sat 9 Oct | 🔥 Heathfield & District | 2nd Sat Oct | high |
| Sun 10 Oct | 🦡 Nevill badge night | 2nd Sun Oct? | 10% (badge default) |
| Sat 16 Oct | 🔥 Hastings Borough | 3rd Sat Oct | high |
| Sat 16 Oct | 🔥 Hailsham | 3rd Sat Oct? | medium |
| Sat 16 Oct | 🔥 Seaford | 3rd Sat Oct? | low |
| Sat 16 Oct | 🔥 East Grinstead | 3rd Sat Oct? | low |
| Wed 20 Oct | 🦡 Firle badge night (The Ram Inn) | Wed before Firle | high |
| Wed 20 Oct | 🦡 Ninfield badge night | Wed before Ninfield? | 10% (badge default) |
| Sat 23 Oct | 🔥 Firle | a week before Newick | high |
| Sat 23 Oct | 🔥 Littlehampton | 4th Sat Oct? | medium |
| Sat 23 Oct | 🔥 Ninfield | 4th Sat Oct? | low |
| Sat 23 Oct | 🔥 Nevill (Lewes) | about two Saturdays before 5 Nov? | low |
| Fri 29 Oct | 🔥 Isfield & Little Horsted | last Friday of October | high |
| Sat 30 Oct | 🔥 Newick | Sat before 5 Nov | high |
| Sat 30 Oct | 🔥 Ewhurst & Staplecross | last Sat Oct | medium |
| Thu 4 Nov | 🦡 Lewes badge night | the evening before Lewes | high |
| Fri 5 Nov | 🔥 Lewes (Cliffe, Borough, Commercial Square, Southover, South Street, Waterloo) | 5 Nov; Sat before if Sun | certain |
| Fri 5 Nov | 🔥 Lindfield | 5 Nov; Sat before if Sun | high |
| Sat 6 Nov | 🔥 Battle | first Sat after 5 Nov | high |
| Sat 6 Nov | 🔥 Chailey | Sat after 5 Nov? | low |
| Fri 12 Nov | 🔥 Hawkhurst Gang | unknown (a Friday in 2026) | low |
| Sat 13 Nov | 🔥 East Hoathly & Halland | nearest Sat to Remembrance Sunday (= the day before) | high |
| Sat 13 Nov | 🔥 Rye & District | a week after Battle | high |
| Sat 13 Nov | 🔥 South Heighton | 2nd Sat Nov | medium |
| Wed 17 Nov | 🦡 Glynde, Beddingham & Firle membership night (Glynde Social Club, 19:00) | Wed before the parade | 10% (badge default) |
| Fri 19 Nov | 🕯️ Glynde, Beddingham & Firle Memorial Parade (Glynde Social Club, 19:30) | Fri after Remembrance Sunday | medium |
| Sat 20 Nov | 🔥 Barcombe | 3rd Sat Nov (or a week after Rye) | high |
| Sat 20 Nov | 🔥 Robertsbridge | 3rd Sat Nov? | medium |
| Sat 27 Nov | 🔥 Chiddingly | 4th Sat Nov | low |


Barcombe has two candidate rules (the 3rd Saturday, or a week after Rye); each
misses one recorded year, but both give 20 Nov in 2027.
The data should keep one rule and record the other in a note.

**Listed with status `unknown` (no events until a date is recorded):**
Cowbeech, Edenbridge (Kent), Icklesham (Robin Hood),
Maresfield, Meeching (Newhaven), Shoreham, Vines Cross, Whatlington Renegades,
Worthing, Cuckfield (fireworks display), and Buxted's badge night (spring 2026
dates conflict: Fri 17 Apr or Fri 22 May).

The Hawkhurst entry's 2027 date, Fri 12 Nov, is a placeholder guess. With no
rule, the builder may instead show it as "date unknown" with no event: see
"no rule at all" above.
