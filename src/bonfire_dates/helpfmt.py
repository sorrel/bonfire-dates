"""Help screens laid out for reading: bold headings, commands grouped by task,
nothing cut short, and examples under every command.

Click measures its columns with ANSI escapes stripped, so headings and terms
can be styled freely; Click's echo drops the styling when piped.
"""
import click

# The order a season is worked in, not the alphabet.
SECTIONS = [
    ("See the season", ["predict", "todo", "list"]),
    ("Keep the calendar", ["sync"]),
    ("Record news", ["confirm", "sources", "evidence"]),
    ("Look after the data", ["check"]),
]

ROUND = [
    ("1. bonfire todo", "what's still only predicted, and where to look"),
    ("2. bonfire confirm …", "record a date you've found or know"),
    ("3. bonfire sync", "update the Bonfire calendar"),
]


class Formatter(click.HelpFormatter):
    def write_heading(self, heading: str) -> None:
        self.write(f"{'':>{self.current_indent}}{click.style(heading, fg='yellow', bold=True)}\n")

    def write_usage(self, prog: str, args: str = "", prefix: str | None = None) -> None:
        super().write_usage(prog, args, click.style("Usage: ", bold=True))


class Context(click.Context):
    formatter_class = Formatter


class Command(click.Command):
    """A command with an Examples section: (command line, what it does) pairs."""
    context_class = Context

    def __init__(self, *args, examples: list[tuple[str, str]] = (), **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.examples = list(examples)

    def format_epilog(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        if self.examples:
            with formatter.section("Examples"):
                for line, what in self.examples:  # what it does, then the line to type
                    formatter.write(f"{'':>{formatter.current_indent}}{click.style(what[0].upper() + what[1:] + ':', dim=True)}\n")
                    formatter.write(f"{'':>{formatter.current_indent + 2}}{click.style(line, fg='cyan')}\n")
        super().format_epilog(ctx, formatter)


class Group(click.Group):
    context_class = Context
    command_class = Command

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        col = max(len(n) for n in self.commands)  # one column for every section
        for title, names in SECTIONS:
            rows = [(n.ljust(col), self.commands[n].get_short_help_str(limit=200)) for n in names if n in self.commands]
            if rows:
                with formatter.section(title):
                    formatter.write_dl(rows)
        listed = {n for _, names in SECTIONS for n in names}
        if extra := [(n, c.get_short_help_str(limit=200)) for n, c in self.commands.items() if n not in listed]:
            with formatter.section("Other"):
                formatter.write_dl(extra)

    def format_epilog(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        with formatter.section("Typical round"):
            formatter.write_dl(ROUND)
        formatter.write_paragraph()
        formatter.write_text("Run any command with -h for its details and examples.")
