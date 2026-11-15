"""Shared pieces of terminal output.

Widths are always measured on plain text and styling applied afterwards,
since an ANSI escape takes no columns. Click strips the styling when the
output isn't a terminal.
"""
import unicodedata

import click

Cell = str | tuple[str, dict]  # plain text, or text with its click.style arguments


def width(text: str) -> int:
    """Terminal columns: wide characters (most emoji) take two; a character
    followed by an emoji variation selector is drawn wide too."""
    cols = 0
    for i, ch in enumerate(text):
        if ch == "\ufe0f" or unicodedata.combining(ch):
            continue
        wide = unicodedata.east_asian_width(ch) in "WF" or text[i + 1:i + 2] == "\ufe0f"
        cols += 2 if wide else 1
    return cols


def _pad(text: str, cols: int) -> str:
    return text + " " * (cols - width(text))


def _text(c: Cell) -> str:
    return c if isinstance(c, str) else c[0]


def _styled(c: Cell, cols: int) -> str:
    """Style the text only and pad outside it, so a line's trailing spaces can be trimmed."""
    text = _text(c)
    shown = click.style(text, **c[1]) if text and not isinstance(c, str) else text
    return shown + " " * max(0, cols - width(text))


def table(rows: list[list[Cell]], header: list[str], indent: str = "  ") -> str:
    """Rows under a bold header and a dim rule; each cell padded plain, then styled."""
    widths = [max(width(_text(r[i])) for r in [header, *rows]) for i in range(len(header))]
    widths_padded = [*widths[:-1], 0]  # the last column isn't padded, so no line ends in spaces
    line = lambda cells: indent + "  ".join(_styled(c, w) for c, w in zip(cells, widths_padded, strict=True))
    rule = indent + "─" * (sum(widths) + 2 * (len(widths) - 1))
    head = indent + click.style("  ".join(_pad(h, w) for h, w in zip(header, widths, strict=True)).rstrip(),
                                bold=True)
    return "\n".join([head, click.style(rule, dim=True), *(line(r).rstrip(" ") for r in rows)])


def heading(text: str) -> str:
    return click.style(text, fg="yellow", bold=True)


def dim(text: str) -> str:
    return click.style(text, dim=True)


def percent_style(p: int, confirmed: bool = False) -> dict:
    if confirmed or p >= 85:
        return {"fg": "green"}
    if p >= 70:
        return {}
    if p >= 35:
        return {"fg": "yellow"}
    return {"fg": "red"}


def percent_cell(p: int, confirmed: bool = False) -> Cell:
    return (f"{p}% ✓" if confirmed else f"{p}%", percent_style(p, confirmed))
