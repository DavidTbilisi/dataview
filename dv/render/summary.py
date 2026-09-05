from pathlib import Path


from dv.core.schema import SchemaInfo
from dv.core.stats import SummaryStats
from dv.render.common import simple_table_heavy, rule
from dv.render.json_out import emit, json_mode
from dv.render.theme import charset, console


TYPE_STYLES = {
    "integer": "green",
    "float":   "yellow",
    "text":    "default",
    "date":    "blue",
    "datetime":"blue",
    "boolean": "magenta",
    "unknown": "red dim",
}


def _type_tag(t: str) -> str:
    style = TYPE_STYLES.get(t, "default")
    return f"[{style}]{t}[/{style}]"


def render_schema(schema: SchemaInfo) -> None:
    if json_mode():
        emit("schema", {
            "path": schema.path,
            "format": schema.format,
            "rows": schema.row_count,
            "columns": [
                {"name": c.name, "type": c.inferred_type, "sql_type": c.duck_type,
                 "missing": c.missing, "unique": c.unique, "example": c.example}
                for c in schema.columns
            ],
        })
        return

    name = Path(schema.path).name
    console.print()
    console.print(rule(f"[bold cyan]schema[/bold cyan]  [dim]{name}[/dim]", style="dim", align="left"))
    console.print()

    table = simple_table_heavy()
    table.add_column("column",    style="bold")
    table.add_column("type")
    table.add_column("missing",   justify="right", style="dim")
    table.add_column("missing %", justify="right", style="dim")
    table.add_column("unique",    justify="right", style="dim")
    table.add_column("example",   style="dim")

    for col in schema.columns:
        pct_missing = col.missing / schema.row_count * 100 if schema.row_count else 0
        pct_unique  = col.unique  / schema.row_count * 100 if schema.row_count else 0
        unique_str  = f"{col.unique} {charset().milestone if pct_unique == 100 else ''}".strip()
        missing_pct = f"{pct_missing:.1f}%" if col.missing else f"[dim]{charset().emdash}[/dim]"
        example     = str(col.example)[:24] if col.example else f"[dim]{charset().emdash}[/dim]"
        table.add_row(
            col.name,
            _type_tag(col.inferred_type),
            str(col.missing) if col.missing else f"[dim]{charset().emdash}[/dim]",
            missing_pct,
            unique_str,
            example,
        )

    console.print(f"  [dim]{schema.row_count:,} rows {charset().bullet} {len(schema.columns)} columns[/dim]")
    console.print()
    console.print(table)


def render_summary(stats: SummaryStats) -> None:
    if json_mode():
        emit("summary", {
            "path": stats.path,
            "format": stats.format,
            "rows": stats.row_count,
            "columns": stats.col_count,
            "numeric_columns": stats.numeric_cols,
            "text_columns": stats.text_cols,
            "date_columns": stats.date_cols,
            "missing_total": stats.missing_total,
            "duplicate_rows": stats.duplicate_count,
            "date_range": list(stats.date_range) if stats.date_range else None,
            "numeric": [
                {"column": n.column, "count": n.count, "min": n.min, "max": n.max,
                 "mean": n.mean, "median": n.median, "std": n.std}
                for n in stats.numeric_stats
            ],
        })
        return

    name = Path(stats.path).name
    console.print()
    console.print(rule(f"[bold cyan]summary[/bold cyan]  [dim]{name}[/dim]", style="dim", align="left"))
    console.print()

    pairs = [
        ("rows",          f"{stats.row_count:,}"),
        ("columns",       str(stats.col_count)),
        ("numeric",       ", ".join(stats.numeric_cols) or f"{charset().emdash}"),
        ("text",          ", ".join(stats.text_cols)    or f"{charset().emdash}"),
        ("dates",         ", ".join(stats.date_cols)    or f"{charset().emdash}"),
        ("missing",       str(stats.missing_total) if stats.missing_total else "[dim]none[/dim]"),
        ("duplicates",    str(stats.duplicate_count) if stats.duplicate_count else "[dim]none[/dim]"),
    ]
    if stats.date_range:
        pairs.insert(2, ("date range", f"{stats.date_range[0]} {charset().arrow} {stats.date_range[1]}"))
    key_w = max(len(k) for k, _ in pairs)
    for key, val in pairs:
        console.print(f"  [dim]{key.ljust(key_w)}[/dim]  {val}")

    if stats.numeric_stats:
        _numeric_table(stats)

    console.print()


def render_missing(schema: SchemaInfo) -> None:
    if json_mode():
        rows = schema.row_count or 1
        emit("missing", [
            {"column": c.name, "missing": c.missing,
             "pct": c.missing / rows * 100}
            for c in schema.columns
        ])
        return

    from dv.render.charts import _bar_text

    name = Path(schema.path).name
    console.print()
    console.print(rule(f"[bold cyan]missing[/bold cyan]  [dim]{name}[/dim]", style="dim", align="left"))
    console.print()

    cols_with_missing = [c for c in schema.columns if c.missing > 0]
    if not cols_with_missing:
        console.print("  [dim]No missing values.[/dim]\n")
        return

    max_missing = max(c.missing for c in cols_with_missing)

    table = simple_table_heavy()
    table.add_column("column",  style="bold")
    table.add_column("missing", justify="right")
    table.add_column("pct",     justify="right", style="dim")
    table.add_column("chart")

    for col in schema.columns:
        if col.missing == 0:
            continue
        pct = col.missing / schema.row_count * 100 if schema.row_count else 0
        bar = _bar_text(col.missing, max_missing, 20)
        table.add_row(col.name, str(col.missing), f"{pct:.1f}%", bar)

    console.print(table)
    console.print()


def _numeric_table(stats: SummaryStats) -> None:
    console.print()
    console.print(rule("[dim]numeric[/dim]", style="dim", align="left"))
    console.print()

    table = simple_table_heavy()
    table.add_column("column",  style="bold")
    table.add_column("count",   justify="right", style="dim")
    table.add_column("min",     justify="right", style="yellow")
    table.add_column("max",     justify="right", style="yellow")
    table.add_column("mean",    justify="right")
    table.add_column("median",  justify="right")
    table.add_column("std",     justify="right", style="dim")

    for ns in stats.numeric_stats:
        table.add_row(
            ns.column,
            f"{ns.count:,}",
            f"{ns.min:g}",
            f"{ns.max:g}",
            f"{ns.mean:.2f}",
            f"{ns.median:.2f}",
            f"{ns.std:.2f}",
        )
    console.print(table)


def render_describe(stats: SummaryStats) -> None:
    if json_mode():
        emit("numeric", [
            {"column": n.column, "count": n.count, "min": n.min, "max": n.max,
             "mean": n.mean, "median": n.median, "std": n.std}
            for n in stats.numeric_stats
        ])
        return

    """Numeric column statistics only — the NUMERIC SUMMARY view."""
    name = Path(stats.path).name
    console.print()
    console.print(rule(f"[bold]describe[/bold]  [dim]{name}[/dim]", style="dim", align="left"))

    if not stats.numeric_stats:
        console.print()
        console.print("  [dim]No numeric columns[/dim]")
        console.print()
        return

    _numeric_table(stats)
    console.print()
