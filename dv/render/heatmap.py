from dv.render.common import ramp
from dv.render.json_out import emit, json_mode
from dv.render.theme import charset, console


def render_heatmap(
    cells: list[tuple[str, str, int]],
    title: str = "",
) -> None:
    """Draw pre-counted (row, column, count) cells. See `core.stats.cross_counts`."""
    if json_mode():
        emit("cells", [{"row": r, "column": c, "count": n} for r, c, n in cells])
        return

    if not cells:
        console.print("[dim]No data[/dim]")
        return

    row_keys = sorted({r for r, _, _ in cells})
    col_keys = sorted({c for _, c, _ in cells})
    counts = {(r, c): n for r, c, n in cells}

    max_count = max(counts.values()) if counts else 1
    col_width = max(len(k) for k in col_keys)
    row_label_width = max(len(k) for k in row_keys)

    if title:
        console.print(f"\n[bold cyan]{title}[/bold cyan]\n")

    header = " " * (row_label_width + 2) + "  ".join(k.ljust(col_width) for k in col_keys)
    console.print(f"  {header}")

    for rk in row_keys:
        cells = []
        for ck in col_keys:
            count = counts.get((rk, ck), 0)
            cells.append(ramp(count / max_count if max_count else 0).ljust(col_width))
        console.print(f"  {rk.ljust(row_label_width)}  {'  '.join(cells)}")

    console.print(f"\n  Legend: {'  '.join(charset().density)}  (none {charset().arrow} high)\n")
