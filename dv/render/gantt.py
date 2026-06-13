from datetime import date

from rich.console import Console
from rich.rule import Rule
from rich.text import Text

console = Console()

_STATUS_KIND = {
    "done":       "done",
    "complete":   "done",
    "completed":  "done",
    "active":     "active",
    "in-progress":"active",
    "inprogress": "active",
    "todo":       "todo",
    "planned":    "todo",
    "blocked":    "blocked",
    "milestone":  "milestone",
    "mile":       "milestone",
}

_STATUS_STYLE = {
    "done":      "green",
    "active":    "cyan",
    "blocked":   "red",
    "milestone": "yellow",
    "todo":      "dim",
}


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


def _bar(
    start: date,
    end: date,
    range_start: date,
    range_end: date,
    width: int,
    kind: str,
    progress: float | None,
) -> Text:
    total_days = (range_end - range_start).days or 1
    start_pos  = min(int((start - range_start).days / total_days * width), width - 1)
    end_pos    = min(int((end   - range_start).days / total_days * width) + 1, width)
    bar_len    = max(1, end_pos - start_pos)

    t = Text(" " * start_pos)
    if kind == "milestone":
        t.append("◆", style="bold yellow")
    elif kind == "done":
        t.append("[", style="dim")
        t.append("#" * bar_len, style="green")
        t.append("]", style="dim")
    elif kind == "active":
        fill_ratio = (progress if progress is not None else 50) / 100
        filled = max(1, int(bar_len * fill_ratio))
        t.append("[", style="dim")
        t.append("#" * filled, style="cyan")
        t.append("-" * (bar_len - filled), style="dim")
        t.append("]", style="dim")
    elif kind == "blocked":
        t.append("[", style="dim")
        t.append("x" * bar_len, style="red")
        t.append("]", style="dim")
    else:  # todo
        t.append("[", style="dim")
        t.append("=" * bar_len, style="dim")
        t.append("]", style="dim")

    return t


def render_gantt(
    rows: list[dict],
    start_col: str,
    end_col: str,
    label_col: str,
    status_col: str | None = None,
    progress_col: str | None = None,
    width: int = 40,
    title: str = "GANTT",
) -> None:
    if not rows:
        console.print("[dim]No data[/dim]")
        return

    parsed = []
    for i, r in enumerate(rows):
        s = _to_date(r.get(start_col))
        e = _to_date(r.get(end_col))
        if s is None or e is None:
            continue
        raw_status = str(r.get(status_col, "todo")).lower() if status_col else "todo"
        kind = _STATUS_KIND.get(raw_status, "todo")
        prog = float(r[progress_col]) if progress_col and r.get(progress_col) is not None else None
        parsed.append((i + 1, str(r.get(label_col, "")), s, e, raw_status, kind, prog))

    if not parsed:
        console.print("[dim]No valid rows[/dim]")
        return

    range_start = min(s for _, _, s, _, _, _, _ in parsed)
    range_end   = max(e for _, _, _, e, _, _, _ in parsed)

    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
    console.print()
    console.print(f"  [dim]Range: {range_start} → {range_end}[/dim]")
    console.print()

    label_w  = max(len(lbl) for _, lbl, *_ in parsed)
    status_w = max(len(st) for _, _, _, _, st, _, _ in parsed) if status_col else 0
    id_w     = len(str(len(parsed)))
    date_w   = 10  # "2026-06-01"

    # Compute available bar width
    term_w  = console.width or 80
    used_w  = id_w + 2 + (status_w + 2 if status_col else 0) + label_w + 2 + date_w + 3 + date_w + 2
    bar_w   = max(10, min(width, term_w - used_w - 4))

    # Header
    hdr = Text("  ")
    hdr.append("#".rjust(id_w), style="bold dim")
    hdr.append("  ")
    if status_col:
        hdr.append("status".ljust(status_w), style="bold dim")
        hdr.append("  ")
    hdr.append(label_col.ljust(label_w), style="bold dim")
    hdr.append("  ")
    hdr.append("start".ljust(date_w), style="bold dim")
    hdr.append("  ")
    hdr.append("end".ljust(date_w), style="bold dim")
    hdr.append("  ")
    hdr.append("timeline", style="bold dim")
    console.print(hdr)
    sep = Text("  " + "─" * (term_w - 4), style="dim")
    console.print(sep)

    for row_id, label, s, e, raw_status, kind, prog in parsed:
        bar = _bar(s, e, range_start, range_end, bar_w, kind, prog)
        line = Text("  ")
        line.append(str(row_id).rjust(id_w), style="dim")
        line.append("  ")
        if status_col:
            style = _STATUS_STYLE.get(kind, "dim")
            line.append(raw_status.ljust(status_w), style=style)
            line.append("  ")
        line.append(label.ljust(label_w), style="bold")
        line.append("  ")
        line.append(str(s).ljust(date_w), style="dim")
        line.append("  ")
        line.append(str(e).ljust(date_w), style="dim")
        line.append("  ")
        line.append_text(bar)
        console.print(line)

    console.print()
    console.print(Text(
        "  Legend: [###] done   [##-] active   [===] todo   [xxx] blocked   ◆ milestone",
        style="dim",
    ))
    console.print()
