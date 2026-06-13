from datetime import date, datetime, timedelta

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


def render_weekmap(
    rows: list[dict],
    date_col: str,
    value_col: str | None = None,
    title: str = "WEEKMAP",
) -> None:
    """Week × weekday grid. Rows = calendar weeks, cols = Mon–Sun."""
    date_vals: dict[date, float] = {}
    for r in rows:
        d = _to_date(r.get(date_col))
        if d is None:
            continue
        v = float(r[value_col]) if value_col and r.get(value_col) is not None else 1.0
        date_vals[d] = date_vals.get(d, 0) + v

    if not date_vals:
        console.print("[dim]No data[/dim]")
        return

    all_dates = sorted(date_vals)
    min_d, max_d = all_dates[0], all_dates[-1]
    week_start = min_d - timedelta(days=min_d.weekday())

    vals = sorted(date_vals.values())
    n = len(vals)
    if n >= 4:
        t1, t2, t3 = vals[n // 4], vals[n // 2], vals[3 * n // 4]
    else:
        mx = max(vals) or 1
        t1, t2, t3 = mx * 0.25, mx * 0.5, mx * 0.75

    def cell(d: date) -> tuple[str, str]:
        v = date_vals.get(d, 0)
        if v <= 0:  return ".", "dim"
        if v <= t1: return "+", "green"
        if v <= t2: return "*", "cyan"
        if v <= t3: return "#", "yellow"
        return "█", "bold red"

    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
    console.print()

    hdr = Text("  " + " " * 11)
    for dn in _WEEKDAY_NAMES:
        hdr.append(f"  {dn}", style="bold dim")
    console.print(hdr)
    console.print()

    cur = week_start
    while cur <= max_d:
        iso = cur.isocalendar()
        label = f"W{iso[1]:02d} {_MONTH_ABBR[cur.month - 1]}"
        line = Text(f"  {label:<11}")
        for d_off in range(7):
            day = cur + timedelta(days=d_off)
            ch, style = cell(day)
            line.append(f"  {ch} ", style=style)
        console.print(line)
        cur += timedelta(days=7)

    console.print()
    console.print(Text("  Legend: . none   + low   * medium   # high   █ max", style="dim"))
    console.print()


def render_rolling(
    items: list[tuple[str, float]],
    window: int = 7,
    title: str = "",
) -> None:
    """Show values with rolling average column."""
    if not items:
        console.print("[dim]No data[/dim]")
        return

    labels = [it[0] for it in items]
    values = [it[1] for it in items]
    n = len(values)

    rolling: list[float] = []
    for i in range(n):
        start = max(0, i - window + 1)
        chunk = values[start : i + 1]
        rolling.append(sum(chunk) / len(chunk))

    _title = (title or f"rolling average (window={window})").upper()
    console.print()
    console.print(Rule(f"[bold]{_title}[/bold]", style="dim", align="left"))
    console.print()

    t = RichTable(box=box.SIMPLE_HEAD, header_style="bold dim", show_edge=False, padding=(0, 1))
    t.add_column("period",          style="dim")
    t.add_column("value",           justify="right")
    t.add_column(f"avg({window})",  justify="right", style="cyan")
    t.add_column("trend",           justify="center", style="dim", width=2)

    for i, (label, v) in enumerate(items):
        ra = rolling[i]
        arrow = "↑" if i > 0 and ra > rolling[i - 1] else ("↓" if i > 0 and ra < rolling[i - 1] else "")
        t.add_row(label, f"{v:,.2f}", f"{ra:,.2f}", arrow)

    console.print(t)
    console.print()


def render_cumulative(
    items: list[tuple[str, float]],
    title: str = "",
) -> None:
    """Show values with cumulative running total and progress bar."""
    if not items:
        console.print("[dim]No data[/dim]")
        return

    total = sum(v for _, v in items)
    if total == 0:
        console.print("[dim]Total is zero[/dim]")
        return

    running = 0.0
    bar_w = 20
    lw = max(len(l) for l, _ in items)
    vw = max(len(f"{v:,.2f}") for _, v in items)
    cw = len(f"{total:,.2f}")

    _title = (title or "cumulative").upper()
    console.print()
    console.print(Rule(f"[bold]{_title}[/bold]", style="dim", align="left"))
    console.print()

    for label, v in items:
        running += v
        pct    = running / total
        filled = int(pct * bar_w)
        bar    = "#" * filled + "-" * (bar_w - filled)
        line = Text(f"  {label:<{lw}}  ")
        line.append(f"{v:>{vw},.2f}", style="default")
        line.append(f"  [", style="dim")
        line.append("#" * filled, style="cyan")
        line.append("-" * (bar_w - filled), style="dim")
        line.append("]", style="dim")
        line.append(f"  {running:>{cw},.2f}", style="bold")
        console.print(line)

    console.print()
    console.print(Text(f"  Total: {total:,.2f}", style="bold"))
    console.print()


def render_duration_summary(
    rows: list[dict],
    start_col: str,
    end_col: str,
    title: str = "DURATIONS",
) -> None:
    """Show duration distribution between two date columns."""
    from dv.render.histogram import render_histogram

    durations: list[float] = []
    for r in rows:
        s = _to_date(r.get(start_col))
        e = _to_date(r.get(end_col))
        if s is not None and e is not None:
            durations.append(float((e - s).days))

    if not durations:
        console.print("[dim]No valid start/end pairs[/dim]")
        return

    sv = sorted(durations)
    n  = len(sv)

    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
    console.print()

    pairs = [
        ("count",  f"{n}"),
        ("min",    f"{sv[0]:.0f} days"),
        ("max",    f"{sv[-1]:.0f} days"),
        ("mean",   f"{sum(durations)/n:.1f} days"),
        ("median", f"{sv[n // 2]:.0f} days"),
    ]
    kw = max(len(k) for k, _ in pairs)
    for k, v in pairs:
        console.print(f"  [dim]{k.ljust(kw)}[/dim]  {v}")
    console.print()

    render_histogram(durations, title=f"{start_col} → {end_col} (days)", bins=8)


def render_before_after(
    before_rows: list[dict],
    after_rows:  list[dict],
    value_col: str,
    cutoff_str: str,
    title: str = "BEFORE / AFTER",
) -> None:
    """Compare aggregate stats before and after a cutoff date."""
    def _stats(rows: list[dict]) -> dict:
        vals = [float(r[value_col]) for r in rows if r.get(value_col) is not None]
        if not vals:
            return {"count": 0, "total": 0.0, "avg": 0.0, "max": 0.0}
        return {
            "count": len(vals),
            "total": sum(vals),
            "avg":   sum(vals) / len(vals),
            "max":   max(vals),
        }

    b = _stats(before_rows)
    a = _stats(after_rows)

    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
    console.print()
    console.print(f"  [dim]cutoff:[/dim]  {cutoff_str}")
    console.print()

    t = RichTable(box=box.SIMPLE_HEAD, header_style="bold dim", show_edge=False, padding=(0, 1))
    t.add_column("metric",  style="dim")
    t.add_column("before",  justify="right")
    t.add_column("after",   justify="right")
    t.add_column("change",  justify="right")

    def _pct(bv: float, av: float) -> Text:
        if bv == 0:
            return Text("—", style="dim")
        pct = (av - bv) / abs(bv) * 100
        s   = f"+{pct:.1f}%" if pct >= 0 else f"{pct:.1f}%"
        return Text(s, style="green" if pct >= 0 else "red")

    metrics = [
        ("count", float(b["count"]), float(a["count"])),
        ("total", b["total"],        a["total"]),
        ("avg",   b["avg"],          a["avg"]),
        ("max",   b["max"],          a["max"]),
    ]
    for metric, bv, av in metrics:
        bfmt = f"{bv:,.0f}" if metric == "count" else f"{bv:,.2f}"
        afmt = f"{av:,.0f}" if metric == "count" else f"{av:,.2f}"
        t.add_row(metric, bfmt, afmt, _pct(bv, av))

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


def render_countdown(
    rows: list[dict],
    date_col: str,
    label_col: str,
    today: date | None = None,
    title: str = "DEADLINES",
) -> None:
    if today is None:
        today = date.today()

    parsed = []
    for r in rows:
        d = _to_date(r.get(date_col))
        label = str(r.get(label_col, ""))
        if d is None:
            continue
        parsed.append((label, d, (d - today).days))

    if not parsed:
        console.print("[dim]No data[/dim]")
        return

    parsed.sort(key=lambda x: x[1])

    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
    console.print()

    t = RichTable(box=box.SIMPLE_HEAD, header_style="bold dim", show_edge=False, padding=(0, 1))
    t.add_column(label_col, style="bold")
    t.add_column("deadline")
    t.add_column("left", justify="right")
    t.add_column("status")

    for label, d, delta in parsed:
        if delta < 0:
            left_str = f"{abs(delta)}d late"
            status = Text("OVERDUE", style="bold red")
        elif delta == 0:
            left_str = "today"
            status = Text("TODAY", style="bold yellow")
        elif delta <= 3:
            left_str = f"{delta}d left"
            status = Text("SOON", style="yellow")
        elif delta <= 7:
            left_str = f"{delta}d left"
            status = Text("upcoming", style="cyan")
        else:
            left_str = f"{delta}d left"
            status = Text("upcoming", style="dim")
        t.add_row(label, str(d), left_str, status)

    console.print(t)
    console.print()


def _parse_dt_hr(val) -> "tuple[date, float] | None":
    """Return (date, fractional_hour) from datetime string, time string, or date."""
    if val is None:
        return None
    s = str(val).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(s[:19], fmt)
            return dt.date(), dt.hour + dt.minute / 60
        except ValueError:
            pass
    if len(s) <= 8 and ":" in s:
        try:
            parts = s.split(":")
            return date.today(), int(parts[0]) + int(parts[1]) / 60
        except (ValueError, IndexError):
            pass
    d = _to_date(val)
    if d:
        return d, 0.0
    return None


def render_sessions(
    rows: list[dict],
    start_col: str,
    end_col: str,
    label_col: str,
    width: int = 48,
    title: str = "SESSION TIMELINE",
) -> None:
    """Multi-day intraday session timeline. start/end should be datetimes or HH:MM times."""
    groups: dict[date, list[tuple[float, float, str]]] = {}
    for r in rows:
        s = _parse_dt_hr(r.get(start_col))
        e = _parse_dt_hr(r.get(end_col))
        label = str(r.get(label_col, "?"))
        if s is None:
            continue
        s_date, s_hr = s
        e_hr = e[1] if e else s_hr + 1.0
        e_hr = max(e_hr, s_hr + 24 / width)
        e_hr = min(e_hr, 24.0)
        groups.setdefault(s_date, []).append((s_hr, e_hr, label))

    if not groups:
        console.print("[dim]No data[/dim]")
        return

    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
    console.print()

    # Ruler: hour markers at 00/06/12/18/24
    ruler = list(" " * (width + 2))
    ticks = list("-" * width)
    for h in (0, 6, 12, 18, 24):
        pos = min(int(h / 24 * width), width - 1)
        lbl = f"{h:02d}"
        for i, ch in enumerate(lbl):
            if pos + i < len(ruler):
                ruler[pos + i] = ch
        ticks[pos] = "|"

    day_lw = 6
    pad = " " * (day_lw + 2)
    console.print(f"  {pad}[dim]{''.join(ruler)}[/dim]")
    console.print(f"  {pad}[dim]{''.join(ticks)}[/dim]")
    console.print()

    for d in sorted(groups):
        line = list(" " * width)
        for s_hr, e_hr, lbl in groups[d]:
            s_pos = int(s_hr / 24 * width)
            e_pos = min(int(e_hr / 24 * width), width)
            bar_len = max(1, e_pos - s_pos)
            for i in range(bar_len):
                p = s_pos + i
                if p >= width:
                    break
                if bar_len == 1:
                    line[p] = "#"
                elif i == 0:
                    line[p] = "|"
                elif i == bar_len - 1:
                    line[p] = "|"
                else:
                    inner = i - 1
                    inner_len = bar_len - 2
                    if inner_len > 1 and inner < len(lbl):
                        line[p] = lbl[inner]
                    else:
                        line[p] = "#"
        day_str = d.strftime("%b %d")
        console.print(f"  {day_str:<{day_lw}}  {''.join(line)}", markup=False)

    console.print()
