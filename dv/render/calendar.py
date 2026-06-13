from datetime import date
import calendar as _cal

from rich.console import Console
from rich.rule import Rule
from rich.text import Text

console = Console()

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
    rows: list[dict],
    date_col: str,
    value_col: str | None = None,
    title: str = "",
) -> None:
    date_vals: dict[date, float] = {}
    for r in rows:
        d = _to_date(r.get(date_col))
        if d is None:
            continue
        v = float(r[value_col]) if value_col and r.get(value_col) is not None else 1.0
        date_vals[d] = date_vals.get(d, 0.0) + v

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
    console.print(Rule(f"[bold]{_title}[/bold]", style="dim", align="left"))
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
