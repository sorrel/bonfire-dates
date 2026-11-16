"""The `bonfire` command. Commands only: the work lives in the other modules."""
import json
from datetime import date, time
from itertools import groupby
from pathlib import Path

import click

from . import config, research, store, sync
from .calendar_app import Calendar, MacCalendar
from .helpfmt import Group
from .display import dim, heading, percent_cell, table
from .load import DataError, load
from .model import SOURCES, Catalogue, Known
from .predict import EMOJI, going_text, predict_one, prediction_year, predictions
from .rules import describe, known_clash, out_of_order, rule_date

NO_EVENT = "no event of its own"


def make_calendar() -> Calendar:
    return MacCalendar(config.CALENDAR_NAME)


def catalogue() -> Catalogue:
    """The societies and confirmed dates, or a readable list of problems and exit 1."""
    try:
        return load(config.SOCIETIES_FILE, config.CONFIRMED_FILE, config.known_file(), config.going_file())
    except DataError as e:
        click.secho("The data has problems:", fg="yellow", bold=True)
        for p in e.problems:
            click.echo(f"  {p}")
        raise SystemExit(1) from None


@click.group(cls=Group, context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 100})
def cli() -> None:
    """Predicted Sussex bonfire nights, each with how sure it is, in their own
    "Bonfire" calendar."""


@cli.command("sync", examples=[("bonfire sync --dry-run", "see every change first; nothing is written"),
                                ("bonfire sync", "write the changes")])
@click.option("--dry-run", is_flag=True, help="Show what would change, and change nothing.")
def sync_cmd(dry_run: bool) -> None:
    """Bring the Bonfire calendar in line with the predictions.

    Covers the next 18 months, whatever the year; once Lewes night has
    passed, this year keeps only known dates. The calendar is read back first: an
    event deleted by hand is restored, a duplicate removed, and events this
    tool didn't make are listed but left alone. Lists each event added,
    restored, moved, updated or removed. Past events are never touched, and
    only the Bonfire calendar is ever changed."""
    cat = catalogue()
    today = date.today()
    state_path = config.data_dir() / "state.json"
    cal = make_calendar()
    if not dry_run and (problem := cal.check_ready()):
        click.secho(problem, fg="yellow")
        raise SystemExit(1)
    click.echo()

    def started(count: int) -> None:
        click.echo(heading(config.CALENDAR_NAME + " calendar") + dim(f"  writing {plural(count, 'change')}…"))

    result = sync.run(cat, cal, state_path, today, dry_run, on_start=started)
    sync_report(result, today, dry_run)
    if result.failed:
        raise SystemExit(1)


ACTIONS = {"add": ("+ added", "green"), "restore": ("↺ restored", "green"), "move": ("→ moved", "cyan"),
           "update": ("~ updated", "blue"),
           "remove": ("− removed", "yellow")}
DRY = {"add": "+ add", "restore": "↺ restore", "move": "→ move", "update": "~ update", "remove": "− remove"}


def plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def sync_report(result: sync.SyncResult, today: date, dry_run: bool) -> None:
    """Each change as a row, then a one-line tally, what the calendar holds, and what's next."""
    name = config.CALENDAR_NAME + " calendar"
    if not result.items:
        click.echo(heading(name) + "  is up to date, nothing to change.")
    else:
        if dry_run:
            click.echo(heading(name) + f"  would make {plural(len(result.items), 'change')}" + dim("  (dry run)"))
        click.echo()
        rows = []
        for i in result.items:
            label, colour = (DRY[i.action], "white") if dry_run else ACTIONS[i.action]
            if i.error:
                label, colour = "✗ failed", "red"
            rows.append([(label, {"fg": colour, "bold": bool(i.error)}), f"{i.day:%a %d %b %Y}", i.title,
                         percent_cell(i.percent, i.confirmed) if i.percent is not None else "",
                         (i.error, {"fg": "yellow"}) if i.error else (i.note, {"dim": True})])
        click.echo(table(rows, ["Change", "Date", "Event", "Sure", ""]))
        click.echo()
        tally = [(sum(1 for i in result.items if i.action == a and not i.error), word)
                 for a, word in (("add", "added"), ("restore", "restored"), ("move", "moved"),
                                 ("update", "updated"),
                                 ("remove", "removed"))]
        tally += [(len(result.failed), "failed"), (result.unchanged, "unchanged")]
        colours = {"added": "green", "restored": "green", "moved": "cyan", "updated": "blue", "removed": "yellow", "failed": "red"}
        parts = [click.style(f"{n} {w}", fg=colours.get(w), bold=True) if n and w in colours else dim(f"{n} {w}")
                 for n, w in tally]
        click.echo("  " + dim(" · ").join(parts) + (dim("  (nothing written)") if dry_run else ""))
    if result.events:
        first, last = result.events[0], result.events[-1]
        verb = "would hold" if dry_run and result.items else "holds"
        missing = sum(1 for i in result.items if i.error and i.action in ("add", "restore"))
        held = f"{len(result.events) - missing} of {len(result.events)} events" if missing else \
            plural(len(result.events), "event")
        click.echo(dim(f"  The calendar {verb} {held}, "
                       f"{first.day:%a %d %b %Y} to {last.day:%a %d %b %Y}."))
        days = (first.day - today).days
        when = "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days"
        click.echo("  " + click.style("Next: ", bold=True) + f"{first.day:%a %d %b}  {first.title}  "
                   + dim(when))
    if result.foreign:
        click.echo()
        click.echo("  " + click.style("Left alone", bold=True)
                   + dim(f"  {plural(len(result.foreign), 'event')} not made by bonfire, never changed"))
        for f in result.foreign:
            click.echo(f"    {f.day:%a %d %b %Y}  {f.title}")
    if result.read_error:
        click.secho(f"  Couldn't read the calendar back ({result.read_error}), so deleted or "
                    "duplicate events weren't checked.", fg="yellow")
    if result.failed:
        click.secho("  Failed writes are tried again on the next sync.", fg="yellow")
    click.echo()


def default_year(cat: Catalogue, today: date) -> int:
    """The season being predicted: next year once this year's Lewes night has passed."""
    return prediction_year(cat, today)


MAX_SPAN = 10


class Years(click.ParamType):
    """A year (2028) or a span of years (2027-2029), as a list of years."""
    name = "years"

    def convert(self, value, param, ctx):
        if isinstance(value, list):
            return value
        first, sep, last = str(value).partition("-")
        try:
            start, end = int(first), int(last) if sep else int(first)
        except ValueError:
            self.fail("use a year like 2028, or a span like 2027-2029", param, ctx)
        if end < start:
            self.fail(f"{value}: the span runs backwards", param, ctx)
        if end - start >= MAX_SPAN:
            self.fail(f"{value}: at most {MAX_SPAN} years at once", param, ctx)
        return list(range(start, end + 1))


def years_or_default(years: list[int] | None, cat: Catalogue) -> list[int]:
    return years or [default_year(cat, date.today())]


@cli.command("predict", examples=[("bonfire predict", "the season being predicted"),
                                   ("bonfire predict 2028", "a later season"),
                                   ("bonfire predict 2027-2029", "several seasons, one after another"),
                                   ("bonfire predict 2027 -v", "with each rule and the years it fits"),
                                   ("bonfire predict --json", "for scripts")])
@click.argument("years", type=Years(), required=False)
@click.option("-v", "--verbose", is_flag=True, help="Add each rule and its evidence.")
@click.option("--json", "as_json", is_flag=True, help="Plain JSON, for scripts.")
def predict_cmd(years: list[int] | None, verbose: bool, as_json: bool) -> None:
    """The season, month by month, with how sure each date is.

    YEARS is a year (2028) or a span (2027-2029). It defaults to the season
    being predicted: this year until Lewes night, then next year. Any year can
    be predicted; the calendar itself only looks 18 months ahead."""
    cat = catalogue()
    found = [p for year in years_or_default(years, cat) for p in predictions(cat, year)]
    if as_json:
        click.echo(json.dumps([{"key": p.key, "society": p.society.id, "name": p.society.name,
                                "date": p.day.isoformat(), "percent": p.percent, "confirmed": p.confirmed,
                                "rule": p.rule_text, "going": going_text(p.hours) if p.hours else None}
                               for p in found], indent=1, ensure_ascii=False))
        return
    going = any(p.hours for p in found)
    for month, group in groupby(found, key=lambda p: p.day.replace(day=1)):
        click.echo()
        click.echo(heading(f"{month:%B %Y}"))
        rows = []
        for p in group:
            row = [f"{p.day:%a %d %b}", p.title, percent_cell(p.percent, p.confirmed)]
            if going:
                row.append((going_text(p.hours), {"fg": "green", "bold": True}) if p.hours else "")
            if verbose:
                years = " ".join(str(k.date.year) for k in p.rating.matches) or "—"
                row += [(p.rule_text, {"dim": True}), years]
            rows.append(row)
        header = ["Date", "Event", "Sure"] + (["Going"] if going else []) + (["Rule", "Fits"] if verbose else [])
        click.echo(table(rows, header))
    click.echo()


@cli.command("list", examples=[("bonfire list", "every society, with the ID other commands take")])
def list_cmd() -> None:
    """Every society and event: its ID, status, rule and the years with known dates."""
    cat = catalogue()
    rows = []
    for s in sorted(cat.societies.values(), key=lambda s: s.name.lower()):
        years = " ".join(sorted({str(k.date.year) for k in s.known})) or "—"
        mark = s.emoji or EMOJI[s.kind]
        rule = NO_EVENT if s.kind == "visiting" else describe(cat, s.rule)
        cells = [f"{mark} {s.name}", s.id, "" if s.status == "active" else s.status, rule, years]
        style = {} if s.status == "active" else {"dim": True}
        rows.append([(c, style) if style else c for c in cells])
    click.echo()
    click.echo(table(rows, ["Society", "ID", "Status", "Rule", "Known"]))
    click.echo()


@cli.command("check", examples=[("bonfire check", "after editing societies.toml")])
def check_cmd() -> None:
    """Check the data files, and show rules that miss a known date.

    Lists every problem at once (file, society and what's wrong) and exits 1
    if there are any."""
    cat = catalogue()  # exits 1, listing every problem, if there are any
    active = [s for s in cat.societies.values() if s.status == "active"]
    click.secho(f"No problems: {len(cat.societies)} entries, {len(active)} active.", fg="green")
    for s in active:
        if s.rule is None:
            continue
        misses = [k for k in s.known if rule_date(cat, s.id, k.date.year) != k.date]
        if misses:
            days = ", ".join(f"{k.date:%d %b %Y}" for k in misses)
            click.echo(dim(f"  {s.name}: rule ({describe(cat, s.rule)}) misses {days}"))
    year = default_year(cat, date.today())
    for s in active:
        if clash := out_of_order(cat, s.id, year):
            other = cat.societies[clash[0]].name
            click.secho(f"  {s.name}: left out of {year}; its predicted date is not in order with "
                        f"{other} ({clash[1]:%a %d %b}), and a badge night always comes first", fg="yellow")


def _date(_ctx, _param, value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise click.BadParameter("use a date like 2027-10-23") from None


@cli.command("confirm", examples=[
    ("bonfire confirm firle 2027-10-23", "a date you know first-hand (kept private)"),
    ("bonfire confirm uckfield 2027-09-04 --source society --url https://…", "from the society's own page"),
])
@click.argument("society")
@click.argument("day", metavar="DATE", callback=_date)
@click.option("--source", type=click.Choice(SOURCES), default="verified", metavar="SOURCE",
              help=f"How the date is known: {', '.join(SOURCES[:-1])} or {SOURCES[-1]}. Default: verified.")
@click.option("--url", metavar="URL", help="Where it was found, if online.")
@click.option("--checked", callback=_date, metavar="DATE", help="When it was checked. Default: today.")
@click.option("--own-event", is_flag=True,
              help="Record a 5 November date even though the rule puts the society's night elsewhere.")
def confirm_cmd(society: str, day: date, source: str, url: str | None, checked: date | None,
                own_event: bool) -> None:
    """Record a society's date for a year; it then counts as 100%.

    SOCIETY is its ID, as `bonfire list` shows (a near miss suggests the
    right one). DATE is like 2027-10-23. A first-hand date (the default
    source, verified) is kept private in data/known.toml; any other goes in
    the public confirmed.toml. Then run `bonfire sync`.

    A 5 November date from a public source is refused for a society whose
    rule puts its night elsewhere: it is usually a council's or a venue's
    fireworks night. Check who runs it; --own-event records it anyway."""
    cat = catalogue()
    sid = research.resolve_id(cat, society)
    if cat.societies[sid].kind == "visiting":
        raise click.ClickException(f"{cat.societies[sid].name} has {NO_EVENT}, so there is no date to record.")
    if clash := known_clash(cat, sid, day):
        other = cat.societies[clash[0]].name
        raise click.ClickException(f"A badge night always comes before its society's night: {other} is known "
                                   f"for {clash[1]:%a %d %b %Y}. Correct that date first if it is wrong.")
    if source != "verified" and not own_event and (ruled := research.fifth_suspect(cat, sid, day)):
        raise click.ClickException(
            f"{cat.societies[sid].name}'s night is usually {ruled:%a %d %b %Y}, not 5 November. Fireworks on "
            "the 5th are often a council's or a venue's, not the society's. If this one really is the "
            "society's own, add --own-event.")
    private = source == "verified"  # known first-hand: kept out of the public repo
    target = config.known_file() if private else config.CONFIRMED_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    research.append_confirmed(target, sid, day, source, url, checked or date.today())
    cat = catalogue()
    in_force = cat.societies[sid].known_in(day.year)
    where = "kept private in data/known.toml" if private else "added to confirmed.toml"
    click.echo(click.style("Recorded: ", fg="green") + f"{cat.societies[sid].name}, {day:%a %d %b %Y} "
               f"({source}, {where})")
    if in_force and in_force.date != day:
        click.secho(f"A better-trusted date stays in force: {in_force.date:%a %d %b %Y} "
                    f"({in_force.evidence.source}).", fg="yellow")
    elif p := predict_one(cat, sid, day.year):
        click.echo(f"  {p.title}: {p.day:%a %d %b %Y}, {p.percent}%")
    click.echo(dim("Run `bonfire sync` to update the calendar."))


@cli.command("todo", examples=[("bonfire todo", "the season being predicted"),
                                ("bonfire todo 2028", "a later season"),
                                ("bonfire todo 2027-2029", "a few seasons ahead")])
@click.argument("years", type=Years(), required=False)
def todo_cmd(years: list[int] | None) -> None:
    """Events still only predicted, soonest first, with where to look.

    YEARS is a year (2028) or a span (2027-2029), one section each. It
    defaults to the season being predicted."""
    cat = catalogue()
    today = date.today()
    for year in years_or_default(years, cat):
        items = research.todo(cat, year, today)
        click.echo()
        click.echo(heading(f"Still to confirm for {year}") + dim(f"  {plural(len(items), 'event')}, soonest first"))
        if items:
            click.echo()
            rows = []
            for p in items:
                checked = research.last_checked(p.society)
                links = "  ".join(p.society.links.values())
                rows.append([f"{p.day:%a %d %b}", p.title, percent_cell(p.percent),
                             f"{checked:%d %b %Y}" if checked else ("never", {"dim": True}), (links, {"dim": True})])
            click.echo(table(rows, ["Date", "Event", "Sure", "Checked", "Where to look"]))
    click.echo()


LABEL = 11  # "Instagram" and two spaces


@cli.command("sources", examples=[("bonfire sources lewes", "why Lewes is rated as it is")])
@click.argument("society")
def sources_cmd(society: str) -> None:
    """One society: its rating, rule, links and the evidence for each date.

    SOCIETY is its ID, as `bonfire list` shows."""
    cat = catalogue()
    s = cat.societies[research.resolve_id(cat, society)]
    year = default_year(cat, date.today())
    p = predict_one(cat, s.id, year)
    click.echo()
    rated = f"  ·  {year}: {p.day:%a %d %b}, rated {p.percent}%" if p else ""
    click.echo(heading(s.name) + dim(f"  {s.kind}, {s.status}{rated}"))
    if s.note:
        click.echo(dim(f"  {s.note}"))
    click.echo()
    def label(text: str) -> str:
        return click.style(f"  {text:<{LABEL}}", bold=True)

    click.echo(label("Rule") + describe(cat, s.rule))
    if s.rule and s.rule.evidence:
        e = s.rule.evidence
        click.echo(dim(" " * (LABEL + 2) + "  ".join(x for x in (e.source, e.note, e.url) if x)))
    for kind, link in s.links.items():
        click.echo(label(kind.capitalize()) + link)
    searched = f"{s.searched:%d %b %Y}" if s.searched else "never"
    click.echo(label("Searched") + searched + dim("  (the last time new sources were looked for)"))
    if s.known:
        click.echo()
        rows = [[f"{k.date:%a %d %b %Y}", k.evidence.source,
                 f"{k.evidence.checked:%d %b %Y}" if k.evidence.checked else ("—", {"dim": True}),
                 "  ".join(x for x in (k.evidence.note, k.evidence.url) if x)]
                for k in sorted(s.known, key=lambda k: k.date)]
        click.echo(table(rows, ["Date", "Source", "Checked", "Note"]))
    folder = research.evidence_dir(config.data_dir(), s.id)
    files = sorted(folder.iterdir()) if folder.exists() else []
    if files:
        click.echo()
        click.echo(click.style("  Local evidence", bold=True))
        for f in files:
            click.echo(dim(f"    {f}"))
    click.echo()


@cli.command("evidence", examples=[("bonfire evidence firle ~/Downloads/poster.jpg", "keep a copy of a poster")])
@click.argument("society")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def evidence_cmd(society: str, file: Path) -> None:
    """Keep a copy of a poster, screenshot or saved page. Never published.

    SOCIETY is its ID, as `bonfire list` shows. FILE is copied into
    data/evidence/SOCIETY/, dated, and never overwrites an earlier copy."""
    sid = research.resolve_id(catalogue(), society)
    target = research.file_evidence(config.data_dir(), sid, file, date.today())
    click.echo(click.style("Filed: ", fg="green") + str(target))


DEFAULT_FROM, DEFAULT_TO = time(18, 0), time(22, 30)


def _time(_ctx, _param, value: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError:
        raise click.BadParameter("use a time like 18:00") from None


def next_year_for(cat: Catalogue, sid: str, today: date) -> int:
    """The year of the society's next event in the calendar, or the season being predicted."""
    ahead = sorted((p for p in sync.wanted(cat, today).values() if p.society.id == sid), key=lambda p: p.day)
    return ahead[0].day.year if ahead else default_year(cat, today)


def going_list(cat: Catalogue, today: date) -> None:
    click.echo()
    if not cat.going:
        click.echo(heading("Going") + dim("  Nothing marked. `bonfire going SOCIETY` marks an event."))
        click.echo()
        return
    in_calendar = sync.wanted(cat, today)
    found = []  # (sort key, row)
    for key, hours in cat.going.items():
        sid, _, year = key.rpartition(":")
        p = predict_one(cat, sid, int(year))
        if p is None:
            found.append(((int(year), date.max.toordinal()), [(year, {"dim": True}), cat.societies[sid].name,
                                                               going_text(hours), ("no date", {"dim": True})]))
            continue
        where = "" if key in in_calendar else ("past" if p.day < today else "not in the calendar")
        found.append(((p.day.year, p.day.toordinal()), [f"{p.day:%a %d %b %Y}", p.title,
                      (going_text(hours), {"fg": "green", "bold": True}), (where, {"dim": True})]))
    rows = [row for _, row in sorted(found, key=lambda f: f[0])]
    click.echo(heading("Going") + dim(f"  {plural(len(rows), 'event')}, kept private in data/going.toml"))
    click.echo()
    click.echo(table(rows, ["Date", "Event", "Hours", ""]))
    click.echo()


@cli.command("going", examples=[("bonfire going seaford", "its next night, 18:00 to 22:30"),
                                 ("bonfire going lewes 2027 --from 17:00 --to 23:30", "your own hours"),
                                 ("bonfire going seaford 2027 --remove", "not going after all"),
                                 ("bonfire going", "what you've marked")])
@click.argument("society", required=False)
@click.argument("year", type=int, required=False)
@click.option("--from", "begin", default="18:00", callback=_time, metavar="TIME",
              help="When you'll be there from. Default: 18:00.")
@click.option("--to", "finish", default="22:30", callback=_time, metavar="TIME",
              help="When you'll leave. Default: 22:30; an earlier time means after midnight.")
@click.option("--remove", is_flag=True, help="Take the mark off: the event goes back to all-day.")
def going_cmd(society: str | None, year: int | None, begin: time, finish: time, remove: bool) -> None:
    """Mark an event you're going to: it becomes a timed event that evening.

    SOCIETY is its ID, as `bonfire list` shows. YEAR defaults to the
    society's next event in the calendar. Marking again replaces the hours.
    Kept private in data/going.toml, never committed. With no SOCIETY, lists
    what's marked. Then run `bonfire sync`."""
    cat = catalogue()
    today = date.today()
    if society is None:
        going_list(cat, today)
        return
    sid = research.resolve_id(cat, society)
    s = cat.societies[sid]
    if s.kind == "visiting":
        raise click.ClickException(f"{s.name} has {NO_EVENT}, so there is nothing to go to.")
    year = year or next_year_for(cat, sid, today)
    key = f"{sid}:{year}"
    marks = dict(cat.going)
    if remove:
        if key not in marks:
            raise click.ClickException(f"{s.name} {year} isn't marked as going.")
        del marks[key]
    else:
        marks[key] = (begin, finish)
    research.write_going(config.going_file(), marks)
    cat = catalogue()
    p = predict_one(cat, sid, year)
    when = f"{p.day:%a %d %b %Y}" if p else str(year)
    if remove:
        click.echo(click.style("Not going: ", fg="yellow") + f"{s.name}, {when}" + dim("  (back to all-day)"))
    else:
        click.echo(click.style("Going: ", fg="green") + f"{p.title if p else s.name}, {when}, "
                   + click.style(going_text((begin, finish)), bold=True) + dim("  (kept private in data/going.toml)"))
        if p is None:
            click.secho(f"  {s.name} has no date for {year} yet, so there's nothing in the calendar to time.",
                        fg="yellow")
        elif key not in sync.wanted(cat, today):
            click.secho("  That event isn't in the calendar's range, so the calendar won't show it.", fg="yellow")
    click.echo(dim("Run `bonfire sync` to update the calendar."))
