"""The `bonfire` command. Commands only: the work lives in the other modules."""
import json
from datetime import date
from itertools import groupby
from pathlib import Path

import click

from . import config, research, store, sync
from .calendar_app import Calendar, MacCalendar
from .display import dim, heading, percent_cell, table
from .load import DataError, load
from .model import SOURCES, Catalogue, Known
from .predict import predict_one, prediction_year, predictions
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


@click.group()
def cli() -> None:
    """Predicted Sussex bonfire nights, in their own calendar."""


@cli.command("sync")
@click.option("--dry-run", is_flag=True, help="Show what would change, and change nothing.")
def sync_cmd(dry_run: bool) -> None:
    """Bring the Bonfire calendar in line with the predictions."""
    cat = catalogue()
    today = date.today()
    state_path = config.data_dir() / "state.json"
    cal = make_calendar()
    if not dry_run and (problem := cal.check_ready()):
        click.secho(problem, fg="yellow")
        raise SystemExit(1)
    todo = sync.plan(cat, store.load(state_path), today)
    count = len(todo.upserts) + len(todo.removals)
    click.echo()
    if count and not dry_run:
        click.echo(heading(config.CALENDAR_NAME + " calendar") + dim(f"  writing {plural(count, 'change')}…"))
    result = sync.run(cat, cal, state_path, today, dry_run)
    sync_report(result, today, dry_run)
    if result.failed:
        raise SystemExit(1)


ACTIONS = {"add": ("+ added", "green"), "move": ("→ moved", "cyan"), "update": ("~ updated", "blue"),
           "remove": ("− removed", "yellow")}
DRY = {"add": "+ add", "move": "→ move", "update": "~ update", "remove": "− remove"}


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
                 for a, word in (("add", "added"), ("move", "moved"), ("update", "updated"),
                                 ("remove", "removed"))]
        tally += [(len(result.failed), "failed"), (result.unchanged, "unchanged")]
        colours = {"added": "green", "moved": "cyan", "updated": "blue", "removed": "yellow", "failed": "red"}
        parts = [click.style(f"{n} {w}", fg=colours.get(w), bold=True) if n and w in colours else dim(f"{n} {w}")
                 for n, w in tally]
        click.echo("  " + dim(" · ").join(parts) + (dim("  (nothing written)") if dry_run else ""))
    if result.events:
        first, last = result.events[0], result.events[-1]
        verb = "would hold" if dry_run and result.items else "holds"
        missing = sum(1 for i in result.items if i.error and i.action == "add")
        held = f"{len(result.events) - missing} of {len(result.events)} events" if missing else \
            plural(len(result.events), "event")
        click.echo(dim(f"  The calendar {verb} {held}, "
                       f"{first.day:%a %d %b %Y} to {last.day:%a %d %b %Y}."))
        days = (first.day - today).days
        when = "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days"
        click.echo("  " + click.style("Next: ", bold=True) + f"{first.day:%a %d %b}  {first.title}  "
                   + dim(when))
    if result.failed:
        click.secho("  Failed writes are tried again on the next sync.", fg="yellow")
    click.echo()


def default_year(cat: Catalogue, today: date) -> int:
    """The season being predicted: next year once this year's Lewes night has passed."""
    return prediction_year(cat, today)


@cli.command("predict")
@click.argument("year", type=int, required=False)
@click.option("-v", "--verbose", is_flag=True, help="Add each rule and its evidence.")
@click.option("--json", "as_json", is_flag=True, help="Plain JSON, for scripts.")
def predict_cmd(year: int | None, verbose: bool, as_json: bool) -> None:
    """The season as a table, month by month, with how sure each date is."""
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


@cli.command("list")
def list_cmd() -> None:
    """Every society and event: status, rule and the years with evidence."""
    cat = catalogue()
    rows = []
    for s in sorted(cat.societies.values(), key=lambda s: s.name.lower()):
        years = " ".join(sorted({str(k.date.year) for k in s.known})) or "—"
        cells = [s.name, s.kind, s.status, describe(cat, s.rule), years]
        style = {} if s.status == "active" else {"dim": True}
        rows.append([(c, style) if style else c for c in cells])
    click.echo()
    click.echo(table(rows, ["Society", "Kind", "Status", "Rule", "Known"]))
    click.echo()


@cli.command("check")
def check_cmd() -> None:
    """Check the data files: unknown anchors and sources, cycles, rules that miss known dates."""
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


@cli.command("confirm")
@click.argument("society")
@click.argument("day", metavar="DATE", callback=_date)
@click.option("--source", type=click.Choice(SOURCES), default="verified", show_default=True,
              help="How the date is known.")
@click.option("--url", help="Where it was found, if online.")
@click.option("--checked", callback=_date, help="When it was checked (default: today).")
def confirm_cmd(society: str, day: date, source: str, url: str | None, checked: date | None) -> None:
    """Record a published or verified date. Then run `bonfire sync`."""
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


@cli.command("todo")
@click.argument("year", type=int, required=False)
def todo_cmd(year: int | None) -> None:
    """Events still only predicted, soonest first, with where to look."""
    cat = catalogue()
    today = date.today()
    year = year or default_year(cat, today)
    items = research.todo(cat, year, today)
    click.echo()
    click.echo(heading(f"Still to confirm for {year}: {len(items)}"))
    for p in items:
        checked = research.last_checked(p.society)
        when = f"checked {checked:%d %b %Y}" if checked else "never checked"
        pc_text, pc_style = percent_cell(p.percent)
        click.echo(f"  {p.day:%a %d %b}  " + click.style(p.title, bold=True) + "  "
                   + click.style(pc_text, **pc_style) + dim(f"  {when}"))
        for kind, link in p.society.links.items():
            click.echo(dim(f"      {kind}: {link}"))
    click.echo()


def _known_line(k: Known) -> str:
    e = k.evidence
    bits = [f"{k.date:%a %d %b %Y}  {e.source}"]
    if e.checked:
        bits.append(f"checked {e.checked:%d %b %Y}")
    if e.note:
        bits.append(e.note)
    return "  ".join(bits) + (f"\n      {e.url}" if e.url else "")


@cli.command("sources")
@click.argument("society")
def sources_cmd(society: str) -> None:
    """Links, and the evidence behind each date and the rule."""
    cat = catalogue()
    s = cat.societies[research.resolve_id(cat, society)]
    click.echo()
    click.echo(heading(s.name) + dim(f"  {s.kind}, {s.status}"))
    for kind, link in s.links.items():
        click.echo(f"  {kind}: {link}")
    click.echo(click.style("  Rule: ", bold=True) + describe(cat, s.rule))
    if s.rule and s.rule.evidence:
        e = s.rule.evidence
        click.echo(dim(f"    {e.source}" + (f": {e.note}" if e.note else "") + (f"  {e.url}" if e.url else "")))
    if s.known:
        click.echo(click.style("  Known dates:", bold=True))
        for k in sorted(s.known, key=lambda k: k.date):
            click.echo("    " + _known_line(k))
    folder = research.evidence_dir(config.data_dir(), s.id)
    files = sorted(folder.iterdir()) if folder.exists() else []
    if files:
        click.echo(click.style("  Local evidence:", bold=True))
        for f in files:
            click.echo(dim(f"    {f}"))
    if s.note:
        click.echo(dim(f"  {s.note}"))
    click.echo()


@cli.command("evidence")
@click.argument("society")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def evidence_cmd(society: str, file: Path) -> None:
    """File a poster, screenshot or saved page locally. It is never published."""
    sid = research.resolve_id(catalogue(), society)
    target = research.file_evidence(config.data_dir(), sid, file, date.today())
    click.echo(click.style("Filed: ", fg="green") + str(target))
