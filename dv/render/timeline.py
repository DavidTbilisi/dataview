from datetime import date, datetime
from rich.console import Console
from rich.rule import Rule
from rich.text import Text

console = Console()

_BAR_CHAR = "▓"
_MILESTONE_CHAR = "◆"
_BAR_STYLE = "cyan"
_MILESTONE_STYLE = "bold yellow"


def _parse_date(val) -> date | None:
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val))
    except Exception:
        return None


def render_timeline(
    rows: list[dict],
    start_col: str,
    end_col: str,
    label_col: str,
    width: int = 60,
) -> None:
    events = []
    for row in rows:
        start = _parse_date(row.get(start_col))
        end = _parse_date(row.get(end_col))
        label = str(row.get(label_col, "?"))
        if start:
            events.append((label, start, end or start))

    if not events:
        console.print("[dim]No data[/dim]")
        return

    global_start = min(e[1] for e in events)
    global_end = max(e[2] for e in events)
    total_days = (global_end - global_start).days or 1

    label_width = max(len(e[0]) for e in events)

    # date label on the right: "Jun 01–03" style
    def _date_str(s: date, e: date) -> str:
        if s == e:
            return s.strftime("%b %d")
        if s.month == e.month:
            return f"{s.strftime('%b %d')}–{e.strftime('%d')}"
        return f"{s.strftime('%b %d')}–{e.strftime('%b %d')}"

    date_strs = [_date_str(s, e) for _, s, e in events]
    date_width = max(len(d) for d in date_strs)

    # bar area: terminal width minus label, date, and padding
    term_width = console.width or 80
    bar_width = max(10, min(width, term_width - label_width - date_width - 8))

    console.print()
    console.print(Rule("[bold cyan]timeline[/bold cyan]", style="dim", align="left"))
    console.print()

    for (label, start, end), date_str in zip(events, date_strs):
        is_milestone = start == end
        offset = int((start - global_start).days / total_days * bar_width)
        span = max(1, int((end - start).days / total_days * bar_width))

        line = Text()
        line.append("  ")
        line.append(label.ljust(label_width), style="default")
        line.append("  ")
        line.append(" " * offset)
        if is_milestone:
            line.append(_MILESTONE_CHAR, style=_MILESTONE_STYLE)
            line.append(" " * (bar_width - offset))
        else:
            line.append(_BAR_CHAR * span, style=_BAR_STYLE)
            line.append(" " * (bar_width - offset - span))
        line.append("  ")
        line.append(date_str, style="dim")
        console.print(line)

    console.print()
