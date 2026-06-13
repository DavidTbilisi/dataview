from datetime import date, timedelta

from rich.console import Console
from rich.rule import Rule
from rich.table import Table as RichTable
from rich.text import Text
from rich import box

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


def render_time_summary(
    rows: list[dict],
    date_col: str,
) -> None:
    from dv.render.charts import render_bar

    dates = [d for r in rows if (d := _to_date(r.get(date_col))) is not None]
    if not dates:
        console.print("[dim]No date data[/dim]")
        return

    unique_dates = sorted(set(dates))
    min_d, max_d  = unique_dates[0], unique_dates[-1]
    total_days    = (max_d - min_d).days + 1
    active_days   = len(unique_dates)

    console.print()
    console.print(Rule("[bold]TIME SUMMARY[/bold]", style="dim", align="left"))
    console.print()

    pairs = [
        ("range",       f"{min_d} → {max_d}"),
        ("total days",  f"{total_days:,}"),
        ("active days", f"{active_days:,}"),
        ("empty days",  f"{total_days - active_days:,}"),
        ("first event", str(min_d)),
        ("last event",  str(max_d)),
    ]
    kw = max(len(k) for k, _ in pairs)
    for k, v in pairs:
        console.print(f"  [dim]{k.ljust(kw)}[/dim]  {v}")
    console.print()

    # By month
    month_counts: dict[str, int] = {}
    for d in dates:
        key = f"{d.year}-{_MONTH_ABBR[d.month - 1]}"
        month_counts[key] = month_counts.get(key, 0) + 1
    month_items = sorted(month_counts.items())
    if month_items:
        console.print(Rule("[dim]by month[/dim]", style="dim", align="left"))
        console.print()
        render_bar([(label.split("-")[1], cnt) for label, cnt in month_items], width=40)

    # By weekday
    wd_counts = [0] * 7
    for d in dates:
        wd_counts[d.weekday()] += 1
    wd_items = [(_WEEKDAY_NAMES[i], wd_counts[i]) for i in range(7)]
    if any(c > 0 for _, c in wd_items):
        console.print(Rule("[dim]by weekday[/dim]", style="dim", align="left"))
        console.print()
        render_bar(wd_items, width=40)


def render_streak(
    rows: list[dict],
    date_col: str,
    title: str = "STREAK",
) -> None:
    dates = [d for r in rows if (d := _to_date(r.get(date_col))) is not None]
    if not dates:
        console.print("[dim]No data[/dim]")
        return

    unique = sorted(set(dates))
    min_d, max_d = unique[0], unique[-1]
    total_days   = (max_d - min_d).days + 1
    date_set     = set(unique)

    # Best streak
    best = curr_best = 1
    for i in range(1, len(unique)):
        if (unique[i] - unique[i - 1]).days == 1:
            curr_best += 1
            best = max(best, curr_best)
        else:
            curr_best = 1

    # Current streak (from end)
    curr = 1
    for i in range(len(unique) - 2, -1, -1):
        if (unique[i + 1] - unique[i]).days == 1:
            curr += 1
        else:
            break

    consistency = len(unique) / total_days * 100 if total_days else 0

    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
    console.print()

    pairs = [
        ("current streak", f"{curr} days"),
        ("best streak",    f"{best} days"),
        ("active days",    f"{len(unique)} / {total_days}"),
        ("consistency",    f"{consistency:.1f}%"),
    ]
    kw = max(len(k) for k, _ in pairs)
    for k, v in pairs:
        console.print(f"  [dim]{k.ljust(kw)}[/dim]  {v}")

    # Recent 28 days
    console.print()
    console.print(Rule("[dim]recent 28 days[/dim]", style="dim", align="left"))
    console.print()
    recent_start = max_d - timedelta(days=27)
    recent_dates = [recent_start + timedelta(days=i) for i in range(28)]

    # Two rows of 14
    for chunk_start in range(0, 28, 14):
        chunk = recent_dates[chunk_start:chunk_start + 14]
        day_row = Text("  ")
        sym_row = Text("  ")
        for dt in chunk:
            day_row.append(f"{dt.day:2d} ", style="dim")
            if dt in date_set:
                sym_row.append(" # ", style="green")
            else:
                sym_row.append(" . ", style="dim")
        console.print(day_row)
        console.print(sym_row)
        console.print()

    console.print(Text("  Legend: # active   . empty", style="dim"))
    console.print()


def render_gaps(
    rows: list[dict],
    date_col: str,
    title: str = "GAPS",
) -> None:
    dates = [d for r in rows if (d := _to_date(r.get(date_col))) is not None]
    if len(dates) < 2:
        console.print("[dim]Not enough data[/dim]")
        return

    unique = sorted(set(dates))
    gaps: list[tuple[date, date, int]] = []
    for i in range(1, len(unique)):
        g = (unique[i] - unique[i - 1]).days
        if g > 1:
            gaps.append((unique[i - 1], unique[i], g))

    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
    console.print()

    if not gaps:
        console.print("  [dim]No gaps (data is consecutive)[/dim]\n")
        return

    gaps.sort(key=lambda x: x[2], reverse=True)
    all_gap_days = [g for _, _, g in gaps]
    avg = sum(all_gap_days) / len(all_gap_days)

    console.print(f"  [dim]gaps found:[/dim]    {len(gaps)}")
    console.print(f"  [dim]longest:[/dim]       {gaps[0][2]} days")
    console.print(f"  [dim]average:[/dim]       {avg:.1f} days")
    console.print()

    t = RichTable(box=box.SIMPLE_HEAD, header_style="bold dim", show_edge=False, padding=(0, 1))
    t.add_column("from",  style="dim")
    t.add_column("to",    style="dim")
    t.add_column("days",  justify="right", style="bold")
    for start, end, days in gaps[:20]:
        t.add_row(str(start), str(end), f"{days}d")
    console.print(t)
    console.print()


def render_compare_periods(
    rows: list[dict],
    period_col: str,
    value_col: str,
    title: str = "",
) -> None:
    if not rows:
        console.print("[dim]No data[/dim]")
        return

    _title = title or f"{value_col} by {period_col}"
    console.print()
    console.print(Rule(f"[bold]{_title.upper()}[/bold]", style="dim", align="left"))
    console.print()

    t = RichTable(box=box.SIMPLE_HEAD, header_style="bold dim", show_edge=False, padding=(0, 1))
    t.add_column(period_col, style="bold")
    t.add_column(value_col,  justify="right")
    t.add_column("change",   justify="right")

    prev: float | None = None
    for r in rows:
        period = str(r[period_col])
        val    = float(r[value_col]) if r.get(value_col) is not None else 0.0
        fmt_v  = f"{val:,.2f}"

        if prev is not None and prev != 0:
            pct = (val - prev) / abs(prev) * 100
            change = Text(f"+{pct:.1f}%", style="green") if pct >= 0 else Text(f"{pct:.1f}%", style="red")
        else:
            change = Text("—", style="dim")

        t.add_row(period, fmt_v, change)
        prev = val

    console.print(t)
    console.print()
