"""The `bonfire` command. Commands only: the work lives in the other modules."""
import json
from datetime import date
from itertools import groupby
from pathlib import Path

import click

from . import config, research, store, sync
from .calendar_app import Calendar, MacCalendar
from .helpfmt import Group
from .display import dim, heading, percent_cell, table
from .load import DataError, load
from .model import SOURCES, Catalogue, Known
from .predict import EMOJI, predict_one, prediction_year, predictions
from .rules import describe, rule_date


def make_calendar() -> Calendar:
    return MacCalendar(config.CALENDAR_NAME)


def catalogue() -> Catalogue:
    """The societies and confirmed dates, or a readable list of problems and exit 1."""
    try:
        return load(config.SOCIETIES_FILE, config.CONFIRMED_FILE, config.known_file())
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

    Covers the rest of this year and all of next; once Lewes night has passed,
    this year keeps only known dates. The calendar is read back first: an
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


@cli.command("predict", examples=[("bonfire predict", "the season being predicted"),
                                   ("bonfire predict 2027 -v", "with each rule and the years it fits"),
                                   ("bonfire predict --json", "for scripts")])
@click.argument("year", type=int, required=False)
@click.option("-v", "--verbose", is_flag=True, help="Add each rule and its evidence.")
@click.option("--json", "as_json", is_flag=True, help="Plain JSON, for scripts.")
def predict_cmd(year: int | None, verbose: bool, as_json: bool) -> None:
    """The season, month by month, with how sure each date is.

    YEAR defaults to the season being predicted: this year until Lewes night,
    then next year."""
    cat = catalogue()
    year = year or default_year(cat, date.today())
    found = predictions(cat, year)
    if as_json:
        click.echo(json.dumps([{"key": p.key, "society": p.society.id, "name": p.society.name,
                                "date": p.day.isoformat(), "percent": p.percent, "confirmed": p.confirmed,
                                "rule": p.rule_text} for p in found], indent=1, ensure_ascii=False))
        return
    for month, group in groupby(found, key=lambda p: p.day.replace(day=1)):
        click.echo()
        click.echo(heading(f"{month:%B %Y}"))
        rows = []
        for p in group:
            row = [f"{p.day:%a %d %b}", p.title, percent_cell(p.percent, p.confirmed)]
            if verbose:
                years = " ".join(str(k.date.year) for k in p.rating.matches) or "—"
                row += [(p.rule_text, {"dim": True}), years]
            rows.append(row)
        header = ["Date", "Event", "Sure"] + (["Rule", "Fits"] if verbose else [])
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
        cells = [f"{mark} {s.name}", s.id, "" if s.status == "active" else s.status, describe(cat, s.rule), years]
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
def confirm_cmd(society: str, day: date, source: str, url: str | None, checked: date | None) -> None:
    """Record a society's date for a year; it then counts as 100%.

    SOCIETY is its ID, as `bonfire list` shows (a near miss suggests the
    right one). DATE is like 2027-10-23. A first-hand date (the default
    source, verified) is kept private in data/known.toml; any other goes in
    the public confirmed.toml. Then run `bonfire sync`."""
    sid = research.resolve_id(catalogue(), society)
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
                                ("bonfire todo 2028", "a later season")])
@click.argument("year", type=int, required=False)
def todo_cmd(year: int | None) -> None:
    """Events still only predicted, soonest first, with where to look.

    YEAR defaults to the season being predicted."""
    cat = catalogue()
    today = date.today()
    year = year or default_year(cat, today)
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
