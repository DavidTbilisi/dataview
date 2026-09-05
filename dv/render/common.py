"""Shared render primitives.

Renderers previously each carried their own copies of these: `_to_date` in
four places, four bar builders, eight progress bars, twelve key/value blocks,
and twenty-six identical Rich table constructions.
"""

from datetime import date

from rich.rule import Rule
from rich.table import Table as RichTable
from rich.text import Text

from dv.render.theme import charset, console, date_format, overflow_mode, table_box

# ── Parsing ───────────────────────────────────────────────────────────────────

def to_date(value) -> date | None:
    """Coerce a cell value to a date, or None if it isn't one."""
    if value is None:
        return None
    if isinstance(value, date) and not hasattr(value, "hour"):
        return value
    if hasattr(value, "date"):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def fmt_date(value) -> str:
    """Format a date cell using the configured date_format."""
    d = to_date(value)
    if d is None:
        return "" if value is None else str(value)
    return d.strftime(date_format())


# ── Numbers ───────────────────────────────────────────────────────────────────

def fmt_num(value, decimals: int = 2) -> str:
    """Format a number with thousands separators; ints stay integral."""
    if value is None:
        return f"{charset().emdash}"
    if isinstance(value, int) or (isinstance(value, float) and value.is_integer()):
        return f"{int(value):,}"
    return f"{value:,.{decimals}f}"


def threshold_style(value: float, good: float, warn: float, invert: bool = False) -> str:
    """green/yellow/red by threshold. Set invert when lower values are better."""
    if invert:
        if value <= good:
            return "green"
        return "yellow" if value <= warn else "red"
    if value >= good:
        return "green"
    return "yellow" if value >= warn else "red"


# ── Bars ──────────────────────────────────────────────────────────────────────

def bar(value: float, max_value: float, width: int) -> str:
    """A proportional bar in the active charset."""
    return charset().bar_of(value, max_value, width)


def gauge(fraction: float, width: int) -> str:
    """A fixed-width [####----] bar in the active charset."""
    return charset().gauge(fraction, width)


def ramp(fraction: float) -> str:
    """A density glyph for a 0..1 fraction."""
    return charset().ramp(fraction)


def bar_width(label_width: int, value_width: int, gutter: int = 8,
              requested: int | None = None) -> int:
    """Bar width that fits the terminal alongside its label and value."""
    if requested is not None:
        return max(1, requested)
    return max(10, (console.width or 80) - label_width - value_width - gutter)


# ── Layout ────────────────────────────────────────────────────────────────────

def rule(title: str = "", style: str = "dim", align: str = "left") -> Rule:
    """A Rule drawn with the active charset's horizontal character."""
    return Rule(title, style=style, align=align, characters=charset().h)


def section(title: str, subtitle: str = "") -> None:
    """A left-aligned rule used as a section header."""
    heading = f"[bold]{title}[/bold]"
    if subtitle:
        heading += f"  [dim]{subtitle}[/dim]"
    console.print()
    console.print(rule(heading))
    console.print()


class _Table(RichTable):
    """A Rich table whose columns default to the charset's overflow mode.

    Rich hardcodes a Unicode ellipsis for overflow="ellipsis", so ASCII mode
    needs every column to fold instead — including ones added after
    construction.
    """

    def add_column(self, *args, **kwargs):
        kwargs.setdefault("overflow", overflow_mode())
        return super().add_column(*args, **kwargs)


def simple_table(*columns: str | tuple) -> RichTable:
    """The project's standard table. Columns are names or (name, kwargs) pairs."""
    table = _Table(box=table_box(), header_style="bold dim",
                   show_edge=False, padding=(0, 1))
    for col in columns:
        if isinstance(col, tuple):
            name, kwargs = col
            kwargs.setdefault("overflow", overflow_mode())
            table.add_column(name, **kwargs)
        else:
            table.add_column(col, overflow=overflow_mode())
    return table


def kv_pairs(pairs: list[tuple[str, object]], indent: str = "  ") -> None:
    """Aligned dim-key / value lines."""
    if not pairs:
        return
    key_width = max(len(str(k)) for k, _ in pairs)
    for key, value in pairs:
        console.print(f"{indent}[dim]{str(key).ljust(key_width)}[/dim]  {value}")


def bar_rows(
    items: list[tuple[str, float]],
    width: int | None = None,
    show_pct: bool = True,
    decimals: int = 2,
    style: str = "cyan",
) -> None:
    """A labelled bar chart with aligned values and optional share percentages."""
    if not items:
        console.print("[dim]No data[/dim]")
        return
    total = sum(v for _, v in items) or 1
    max_v = max(v for _, v in items) or 1
    label_w = max(len(str(label)) for label, _ in items)
    val_strs = [f"{v:,.{decimals}f}" for _, v in items]
    val_w = max(len(s) for s in val_strs)
    w = bar_width(label_w, val_w, gutter=14 if show_pct else 8, requested=width)

    for (label, value), val_str in zip(items, val_strs, strict=True):
        line = Text("  ")
        line.append(str(label).ljust(label_w))
        line.append("  ")
        line.append(bar(value, max_v, w).ljust(w), style=style)
        line.append(f"  {val_str.rjust(val_w)}")
        if show_pct:
            line.append(f"  {value / total * 100:>5.1f}%", style="dim")
        console.print(line)


def simple_table_heavy(*columns: str | tuple) -> RichTable:
    """`simple_table` with a rule under the body as well as the header."""
    table = simple_table(*columns)
    table.box = table_box(heavy=True)
    table.header_style = "dim"
    return table
