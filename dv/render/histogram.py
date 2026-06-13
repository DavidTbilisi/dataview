from rich.console import Console
from rich.rule import Rule
from rich.text import Text

from dv.render.charts import _bar_unicode, _BAR_COLOR

console = Console()


def render_histogram(
    values: list[float],
    title: str = "",
    bins: int = 10,
    width: int | None = None,
) -> None:
    if not values:
        console.print("[dim]No data[/dim]")
        return

    mn, mx = min(values), max(values)
    if mn == mx:
        console.print(f"[dim]All values are {mn}[/dim]")
        return

    step = (mx - mn) / bins
    bucket_counts = [0] * bins
    for v in values:
        idx = min(int((v - mn) / step), bins - 1)
        bucket_counts[idx] += 1

    max_count = max(bucket_counts) or 1

    # Build labels: "lo – hi" with consistent precision
    labels = []
    for i in range(bins):
        lo = mn + i * step
        hi = mn + (i + 1) * step
        precision = 0 if lo >= 1000 else (1 if lo >= 10 else 2)
        labels.append(f"{lo:.{precision}f} – {hi:.{precision}f}")
    label_width = max(len(l) for l in labels)

    count_strs = [str(c) for c in bucket_counts]
    count_width = max(len(s) for s in count_strs)

    term_width = console.width or 80
    bar_width = width or max(10, term_width - label_width - count_width - 8)

    if title:
        console.print()
        console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
        console.print()

    for label, count, count_str in zip(labels, bucket_counts, count_strs):
        line = Text("  ")
        line.append(label.ljust(label_width), style="dim")
        line.append("  ")
        line.append_text(_bar_unicode(count, max_count, bar_width))
        filled = int(count / max_count * bar_width)
        line.append(" " * (bar_width - filled + 1))
        line.append(count_str, style="bold" if count == max(bucket_counts) else "default")
        console.print(line)

    console.print()
