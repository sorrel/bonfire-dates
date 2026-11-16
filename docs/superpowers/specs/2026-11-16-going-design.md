# Events you're going to: timed, not all-day

## Why

The Bonfire calendar shows each event as an all-day entry. For the events the
user is actually going to, the calendar should show the evening they'll be
out (say 18:00 to 22:30), so it sits properly alongside the rest of their day.

## Goals

- Mark one event (a society in one year) as going, with its hours.
- A marked event becomes a timed event on its night; unmarking makes it
  all-day again. Sync updates it in place.

## Non-goals and anti-goals

- No "always going" setting per society: going is decided each year (some
  years a society is skipped even when it is the only event that night).
- Nothing about going may reach a tracked file. It lives only in gitignored
  `data/going.toml`, like first-hand dates in `data/known.toml`.

## Approaches

1. **Private mark file keyed by society and year** (chosen). The mark follows
   the event if its predicted date moves or is confirmed.
2. A field in `societies.toml` or `confirmed.toml`: rejected, it would publish
   which events the user attends.
3. Keyed by date: rejected, a moved prediction would silently lose the mark.

## Design

- `data/going.toml`: `[[going]]` entries with `society`, `year`, `from`,
  `to` (local times). `load` reads it into `Catalogue.going`
  (`"id:year"` → hours) and collects its problems like any other file.
- `bonfire going [SOCIETY] [YEAR] [--from 18:00] [--to 22:30] [--remove]`.
  YEAR defaults to the season being predicted. With no SOCIETY, lists what is
  marked. Marking again replaces the hours. Refuses a `visiting` society or one
  that isn't active.
- Hours override a society's `start` and the fixed 3-hour length. An end at or
  before the start runs past midnight.
- Notes gain "Going 18:00–22:30"; the title is unchanged. `predict` shows the
  hours in a Going column.

## Left to the builder

Layout of the `going` listing; wording of messages.
