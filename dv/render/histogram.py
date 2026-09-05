from rich.text import Text

from dv.core.stats import Bin
from dv.render.charts import _bar_text
from dv.render.common import section
from dv.render.json_out import emit, json_mode
from dv.render.theme import charset, console


def render_histogram(
    bins: list[Bin],
    title: str = "",
    width: int | None = None,
) -> None:
    """Draw pre-computed buckets. See `core.stats.numeric_bins` for the maths."""
    if json_mode():
        emit("bins", [{"lo": b.lo, "hi": b.hi, "count": b.count} for b in bins])
        return

    if not bins:
        console.print("[dim]No data[/dim]")
        return
    if len(bins) == 1 and bins[0].lo == bins[0].hi:
        console.print(f"[dim]All values are {bins[0].lo:g}[/dim]",
                      highlight=False)
        return

    bucket_counts = [b.count for b in bins]
    max_count = max(bucket_counts) or 1

    # Build labels: "lo – hi" with consistent precision
    labels = []
    for b in bins:
        precision = 0 if b.lo >= 1000 else (1 if b.lo >= 10 else 2)
        labels.append(f"{b.lo:.{precision}f} {charset().dash} {b.hi:.{precision}f}")
    label_width = max(len(label) for label in labels)

    count_strs = [str(c) for c in bucket_counts]
    count_width = max(len(s) for s in count_strs)

    term_width = console.width or 80
    bar_width = width or max(10, term_width - label_width - count_width - 8)

    if title:
        section(title)

    for label, count, count_str in zip(labels, bucket_counts, count_strs, strict=True):
        line = Text("  ")
        line.append(label.ljust(label_width), style="dim")
        line.append("  ")
        line.append_text(_bar_text(count, max_count, bar_width))
        filled = int(count / max_count * bar_width)
        line.append(" " * (bar_width - filled + 1))
        line.append(count_str, style="bold" if count == max(bucket_counts) else "default")
        console.print(line)

    console.print()
