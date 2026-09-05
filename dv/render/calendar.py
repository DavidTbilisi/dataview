from datetime import date
import calendar as _cal

from rich.text import Text
from dv.render.common import rule
from dv.render.json_out import emit, json_mode
from dv.render.theme import console


_WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _to_date(d) -> date | None:
    if d is None:
        return None
    if isinstance(d, date) and not hasattr(d, 'hour'):
        return d
    if hasattr(d, 'date'):
        return d.date()
    try:
        return date.fromisoformat(str(d)[:10])
    except (ValueError, TypeError):
        return None


def _sym(v: float, low: float, med: float, high: float) -> str:
    if v <= 0:
        return "."
    if v < low:
        return "+"
    if v < med:
        return "*"
    return "#"


def render_calendar(
    totals: list[tuple[str, float]],
    title: str = "",
) -> None:
    """Draw one cell per day. See `core.stats.daily_totals` for the aggregation."""
    if json_mode():
        emit("days", [{"date": d, "value": v} for d, v in totals])
        return

    date_vals: dict[date, float] = {}
    for day, value in totals:
        d = _to_date(day)
        if d is not None:
            date_vals[d] = date_vals.get(d, 0.0) + value

    if not date_vals:
        console.print("[dim]No data[/dim]")
        return

    pos_vals = sorted(v for v in date_vals.values() if v > 0)
    n = len(pos_vals)
    if n >= 4:
        low  = pos_vals[n // 4]
        med  = pos_vals[n // 2]
        high = pos_vals[3 * n // 4]
    elif n > 0:
        mx = max(pos_vals)
        low, med, high = mx * 0.25, mx * 0.5, mx * 0.75
    else:
        low, med, high = 1.0, 2.0, 3.0

    min_d = min(date_vals.keys())
    max_d = max(date_vals.keys())

    months: list[tuple[int, int]] = []
    y, m = min_d.year, min_d.month
    while (y, m) <= (max_d.year, max_d.month):
        months.append((y, m))
        m += 1
        if m > 12:
            m, y = 1, y + 1

    # Build grid: grid[weekday] = [cell_str_per_month]
    grid: list[list[str]] = []
    for wd in range(7):
        row_cells: list[str] = []
        for year, month in months:
            days_in = _cal.monthrange(year, month)[1]
            cell = ""
            for day in range(1, days_in + 1):
                d = date(year, month, day)
                if d.weekday() == wd:
                    cell += _sym(date_vals.get(d, 0.0), low, med, high)
            row_cells.append(cell)
        grid.append(row_cells)

    max_cell = max((len(c) for row in grid for c in row), default=5)
    col_w = max(max_cell, 3) + 4  # data chars + separator

    _title = title or "CALENDAR"
    console.print()
    console.print(rule(f"[bold]{_title}[/bold]", style="dim", align="left"))
    console.print()

    label_w = 3
    sep = "  "
    prefix = " " * (label_w + len(sep))
    header = prefix + "".join(_MONTH_ABBR[m - 1].ljust(col_w) for _, m in months)
    console.print(Text(header, style="dim"))
    console.print()

    for wd, row_cells in enumerate(grid):
        line = Text(_WEEKDAY_NAMES[wd] + sep)
        for cell in row_cells:
            line.append(cell.ljust(col_w))
        console.print(line)

    console.print()
    console.print(Text("  Legend: . none   + low   * medium   # high", style="dim"))
    console.print()
