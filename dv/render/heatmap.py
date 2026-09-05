from dv.render.common import ramp
from dv.render.theme import charset, console



def render_heatmap(
    rows: list[dict],
    row_col: str,
    col_col: str,
    title: str = "",
) -> None:
    if not rows:
        console.print("[dim]No data[/dim]")
        return

    row_keys = sorted(set(str(r[row_col]) for r in rows))
    col_keys = sorted(set(str(r[col_col]) for r in rows))

    counts: dict[tuple, int] = {}
    for r in rows:
        key = (str(r[row_col]), str(r[col_col]))
        counts[key] = counts.get(key, 0) + 1

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
