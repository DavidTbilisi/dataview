from builtins import sum as builtins_sum
from rich.console import Console
from rich.rule import Rule
from rich.table import Table as RichTable
from rich import box

from dv.core.datasource import ResultView

console = Console()


def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    return str(value) if value is not None else ""


def render_pivot(
    rows: list[dict],
    row_label: str,
    col_order: list[str],
    title: str = "",
    is_float: bool = True,
) -> None:
    pivot: dict[str, dict[str, float]] = {}
    row_order: list[str] = []

    for r in rows:
        rv = str(r["_row"])
        cv = str(r["_col"])
        val = float(r["_val"]) if r["_val"] is not None else 0.0
        if rv not in pivot:
            pivot[rv] = {}
            row_order.append(rv)
        pivot[rv][cv] = val

    if not row_order:
        console.print("[dim]No data[/dim]")
        return

    if title:
        console.print()
        console.print(Rule(f"[bold]{title.upper()}[/bold]", style="dim", align="left"))
        console.print()

    def fmt(v: float) -> str:
        return f"{v:,.2f}" if is_float else str(int(v))

    table = RichTable(box=box.SIMPLE_HEAD, header_style="bold dim", show_edge=False, padding=(0, 1))
    table.add_column(row_label, style="bold")
    for col in col_order:
        table.add_column(col, justify="right")
    table.add_column("Total", justify="right", style="bold cyan")

    for rv in row_order:
        rd = pivot[rv]
        total = builtins_sum(rd.values())
        cells = [rv]
        for col in col_order:
            v = rd.get(col)
            cells.append(fmt(v) if v is not None else "[dim]—[/dim]")
        cells.append(fmt(total))
        table.add_row(*cells)

    console.print(table)
    console.print()


def render_table(
    result: ResultView,
    title: str = "",
    row_num: bool = False,
    truncate: int | None = None,
) -> None:
    if title:
        console.print()
        console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
        console.print()

    table = RichTable(
        box=box.SIMPLE_HEAD,
        header_style="bold dim",
        show_edge=False,
        padding=(0, 1),
    )
    if row_num:
        table.add_column("#", style="dim", justify="right")
    for col in result.columns:
        table.add_column(col)
    for i, row in enumerate(result.rows):
        cells = []
        if row_num:
            cells.append(str(i + 1))
        for c in result.columns:
            v = _fmt(row.get(c, ""))
            if truncate and len(v) > truncate:
                v = v[:truncate - 3] + "..."
            cells.append(v)
        table.add_row(*cells)
    console.print(table)
    console.print()


def render_top(
    rows: list[dict],
    column_name: str,
    value_name: str,
    title: str = "",
) -> None:
    if not rows:
        console.print("[dim]No data[/dim]")
        return

    total_sum = builtins_sum(
        float(r["total"]) for r in rows if r.get("total") is not None
    )

    _title = title or f"TOP {column_name.upper()} BY {value_name.upper()}"
    console.print()
    console.print(Rule(f"[bold]{_title}[/bold]", style="dim", align="left"))
    console.print()

    table = RichTable(box=box.SIMPLE_HEAD, header_style="bold dim", show_edge=False, padding=(0, 1))
    table.add_column("rank",  style="dim", justify="right")
    table.add_column(column_name, style="bold")
    table.add_column(value_name,  justify="right")
    table.add_column("share",     justify="right", style="dim")

    for i, row in enumerate(rows):
        val = float(row["total"]) if row.get("total") is not None else 0.0
        share = val / total_sum * 100 if total_sum else 0
        table.add_row(
            str(i + 1),
            str(row[column_name]),
            f"{val:,.2f}",
            f"{share:.1f}%",
        )

    console.print(table)
    console.print()
