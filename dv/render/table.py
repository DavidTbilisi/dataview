
from dv.core.datasource import ResultView
from dv.render.common import section, simple_table
from dv.render.json_out import emit, json_mode
from dv.render.theme import charset, console, err_console, overflow_mode


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
    if json_mode():
        emit("rows", [
            {row_label: r["_row"], "column": r["_col"], "value": r["_val"]}
            for r in rows
        ])
        return

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
        section(title.upper())

    def fmt(v: float) -> str:
        return f"{v:,.2f}" if is_float else str(int(v))

    table = simple_table()
    table.add_column(row_label, style="bold")
    for col in col_order:
        table.add_column(col, justify="right")
    table.add_column("Total", justify="right", style="bold cyan")

    for rv in row_order:
        rd = pivot[rv]
        total = sum(rd.values())
        cells = [rv]
        for col in col_order:
            v = rd.get(col)
            cells.append(fmt(v) if v is not None else f"[dim]{charset().emdash}[/dim]")
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
    if json_mode():
        emit("rows", result.rows)
        meta = result.metadata
        if meta.get("truncated"):
            # The cap still applies, but a script must not be told quietly that
            # it received everything.
            total = meta.get("total")
            of = f" of {total:,}" if total is not None else ""
            err_console.print(
                f"[yellow]Warning:[/yellow] emitted {meta['shown']:,}{of} rows "
                f"- raise with --limit, or --all"
            )
        return

    if title:
        section(title)

    table = simple_table()
    if row_num:
        table.add_column("#", style="dim", justify="right", overflow=overflow_mode())
    for col in result.columns:
        table.add_column(col, overflow=overflow_mode())
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

    meta = result.metadata
    if meta.get("truncated"):
        total = meta.get("total")
        of = f" of {total:,}" if total is not None else ""
        # highlight=False: this is a prose hint, not data. Rich's
        # highlighter would paint the counts cyan *inside* the dim span,
        # which reads as an accident rather than emphasis.
        console.print(
            f"  [dim]showing {meta['shown']:,}{of} rows "
            f"{charset().emdash} raise with --limit, or --all[/dim]",
            highlight=False,
        )
    console.print()


def render_top(
    rows: list[dict],
    column_name: str,
    value_name: str,
    title: str = "",
) -> None:
    if json_mode():
        total = sum(float(r["total"]) for r in rows if r.get("total") is not None)
        emit("rows", [
            {
                "rank": i + 1,
                column_name: r[column_name],
                value_name: float(r["total"] or 0),
                "share": (float(r["total"] or 0) / total * 100) if total else 0.0,
            }
            for i, r in enumerate(rows)
        ])
        return

    if not rows:
        console.print("[dim]No data[/dim]")
        return

    total_sum = sum(
        float(r["total"]) for r in rows if r.get("total") is not None
    )

    _title = title or f"TOP {column_name.upper()} BY {value_name.upper()}"
    section(_title)

    table = simple_table()
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
