from rich.console import Console
from rich.rule import Rule
from rich.text import Text

console = Console()

# Sub-character block precision: space + 8 fractions
_FRAC = " ▏▎▍▌▋▊▉█"
_SPARK = "▁▂▃▄▅▆▇█"
_BAR_COLOR = "cyan"
_FRAC_COLOR = "cyan"


def _bar_unicode(value: float, max_value: float, width: int) -> Text:
    """Full-block bar with sub-character fractional tail."""
    if max_value == 0:
        return Text(" " * width)
    eighths = int(value / max_value * width * 8)
    full = eighths // 8
    frac = eighths % 8
    t = Text()
    if full:
        t.append("█" * full, style=_BAR_COLOR)
    if frac:
        t.append(_FRAC[frac], style=_FRAC_COLOR)
    return t


def render_bar(
    rows: list[tuple[str, int | float]],
    title: str = "",
    width: int | None = None,
    sort: bool = False,
) -> None:
    if not rows:
        console.print("[dim]No data[/dim]")
        return

    if sort:
        rows = sorted(rows, key=lambda r: r[1], reverse=True)

    max_val = max(v for _, v in rows) or 1
    label_width = max(len(str(k)) for k, _ in rows)
    val_strs = [f"{v:,.2f}" if isinstance(v, float) else str(v) for _, v in rows]
    val_width = max(len(s) for s in val_strs)

    # leave room for: indent(2) + label + gap(2) + bar + gap(2) + value
    term_width = console.width or 80
    bar_width = width or max(10, term_width - label_width - val_width - 8)

    if title:
        console.print()
        console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
        console.print()

    for (label, value), val_str in zip(rows, val_strs):
        line = Text("  ")
        line.append(str(label).ljust(label_width), style="default")
        line.append("  ")
        line.append_text(_bar_unicode(float(value), float(max_val), bar_width))
        # pad to align values
        filled = int(float(value) / float(max_val) * bar_width)
        line.append(" " * (bar_width - filled + 1))
        line.append(val_str, style="dim")
        console.print(line)

    console.print()


_DOT = "◆"
_DOT_STYLE = "cyan"
_DOT_MULTI_STYLE = "bold yellow"   # cell holds >1 point


def render_scatter(
    points: list[tuple[float, float]],
    x_label: str = "x",
    y_label: str = "y",
    width: int | None = None,
    height: int = 20,
) -> None:
    if not points:
        console.print("[dim]No data[/dim]")
        return

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    x_rng = x_max - x_min or 1.0
    y_rng = y_max - y_min or 1.0

    term_width = console.width or 80
    # y-axis label column uses up to 8 chars; leave 4 for right margin
    y_label_w = max(len(f"{y_max:.4g}"), len(f"{y_min:.4g}"), 3) + 1
    plot_w = width or max(20, term_width - y_label_w - 5)
    plot_h = height

    # build grid: grid[row][col] = count of points
    grid: list[list[int]] = [[0] * plot_w for _ in range(plot_h)]
    for x, y in points:
        col = min(int((x - x_min) / x_rng * (plot_w - 1)), plot_w - 1)
        row = min(int((y_max - y) / y_rng * (plot_h - 1)), plot_h - 1)
        grid[row][col] += 1

    # y-axis ticks: top, mid, bottom
    tick_rows = {0: y_max, plot_h // 2: (y_max + y_min) / 2, plot_h - 1: y_min}

    console.print()
    console.print(Rule(f"[bold]{x_label} vs {y_label}[/bold]", style="dim", align="left"))
    console.print()
    console.print(Text("  " + y_label, style="dim"))
    console.print()

    for r in range(plot_h):
        line = Text()
        tick_val = tick_rows.get(r)
        if tick_val is not None:
            label = f"{tick_val:.4g}"
            line.append(label.rjust(y_label_w), style="dim")
            line.append(" │", style="dim")
        else:
            line.append(" " * y_label_w + "  ", style="dim")

        for c in range(plot_w):
            n = grid[r][c]
            if n == 0:
                line.append(" ")
            elif n == 1:
                line.append(_DOT, style=_DOT_STYLE)
            else:
                line.append(_DOT, style=_DOT_MULTI_STYLE)

        console.print(line)

    # x-axis line
    axis = Text()
    axis.append(" " * (y_label_w + 1), style="dim")
    axis.append("└" + "─" * plot_w, style="dim")
    console.print(axis)

    # x-axis tick labels: left, mid, right
    x_tick_line = Text()
    x_tick_line.append(" " * (y_label_w + 2))
    left_s = f"{x_min:.4g}"
    mid_s = f"{(x_min + x_max) / 2:.4g}"
    right_s = f"{x_max:.4g}"
    mid_pos = (plot_w - len(mid_s)) // 2
    right_pos = plot_w - len(right_s)
    row_chars = [" "] * plot_w
    for i, ch in enumerate(left_s):
        if i < plot_w:
            row_chars[i] = ch
    for i, ch in enumerate(mid_s):
        p = mid_pos + i
        if 0 <= p < plot_w:
            row_chars[p] = ch
    for i, ch in enumerate(right_s):
        p = right_pos + i
        if 0 <= p < plot_w:
            row_chars[p] = ch
    x_tick_line.append("".join(row_chars), style="dim")
    console.print(x_tick_line)

    # x-axis label centered below
    pad = y_label_w + 2 + (plot_w - len(x_label)) // 2
    console.print(Text(" " * pad + x_label, style="dim"))
    console.print()


def render_composition(
    rows: list[tuple[str, float]],
    title: str = "",
    width: int | None = None,
) -> None:
    if not rows:
        console.print("[dim]No data[/dim]")
        return

    total = sum(v for _, v in rows) or 1.0
    label_width = max(len(str(k)) for k, _ in rows)
    term_width  = console.width or 80
    bar_width   = width or max(10, term_width - label_width - 14)

    if title:
        console.print()
        console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
        console.print()

    for label, value in rows:
        pct = value / total * 100
        pct_str = f"{pct:.1f}%"
        line = Text("  ")
        line.append(str(label).ljust(label_width), style="default")
        line.append("  ")
        line.append(pct_str.rjust(6), style="dim")
        line.append("  ")
        line.append_text(_bar_unicode(pct, 100.0, bar_width))
        console.print(line)

    console.print()
    total_str = f"{total:,.2f}" if isinstance(total, float) else str(int(total))
    console.print(Text(f"  Total: {total_str}", style="dim"))
    console.print()


def render_sparkline(values: list[float], title: str = "") -> None:
    if not values:
        console.print("[dim]No data[/dim]")
        return

    mn, mx = min(values), max(values)
    rng = mx - mn or 1

    line = Text("  ")
    for v in values:
        idx = int((v - mn) / rng * 7)
        line.append(_SPARK[idx], style=_BAR_COLOR)

    if title:
        console.print()
        console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
        console.print()
    console.print(line)
    console.print()
