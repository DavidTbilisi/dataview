from pathlib import Path

from rich.console import Console
from rich.table import Table as RichTable
from rich.rule import Rule
from rich import box

from dv.core.schema import SchemaInfo
from dv.core.stats import SummaryStats

console = Console()

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
    name = Path(schema.path).name
    console.print()
    console.print(Rule(f"[bold cyan]schema[/bold cyan]  [dim]{name}[/dim]", style="dim", align="left"))
    console.print()

    table = RichTable(box=box.SIMPLE, header_style="dim", show_edge=False, padding=(0, 1))
    table.add_column("column",    style="bold")
    table.add_column("type")
    table.add_column("missing",   justify="right", style="dim")
    table.add_column("missing %", justify="right", style="dim")
    table.add_column("unique",    justify="right", style="dim")
    table.add_column("example",   style="dim")

    for col in schema.columns:
        pct_missing = col.missing / schema.row_count * 100 if schema.row_count else 0
        pct_unique  = col.unique  / schema.row_count * 100 if schema.row_count else 0
        unique_str  = f"{col.unique} {'◆' if pct_unique == 100 else ''}".strip()
        missing_pct = f"{pct_missing:.1f}%" if col.missing else "[dim]—[/dim]"
        example     = str(col.example)[:24] if col.example else "[dim]—[/dim]"
        table.add_row(
            col.name,
            _type_tag(col.inferred_type),
            str(col.missing) if col.missing else "[dim]—[/dim]",
            missing_pct,
            unique_str,
            example,
        )

    console.print(f"  [dim]{schema.row_count:,} rows · {len(schema.columns)} columns[/dim]")
    console.print()
    console.print(table)


def render_summary(stats: SummaryStats) -> None:
    name = Path(stats.path).name
    console.print()
    console.print(Rule(f"[bold cyan]summary[/bold cyan]  [dim]{name}[/dim]", style="dim", align="left"))
    console.print()

    pairs = [
        ("rows",          f"{stats.row_count:,}"),
        ("columns",       str(stats.col_count)),
        ("numeric",       ", ".join(stats.numeric_cols) or "—"),
        ("text",          ", ".join(stats.text_cols)    or "—"),
        ("dates",         ", ".join(stats.date_cols)    or "—"),
        ("missing",       str(stats.missing_total) if stats.missing_total else "[dim]none[/dim]"),
        ("duplicates",    str(stats.duplicate_count) if stats.duplicate_count else "[dim]none[/dim]"),
    ]
    if stats.date_range:
        pairs.insert(2, ("date range", f"{stats.date_range[0]} → {stats.date_range[1]}"))
    key_w = max(len(k) for k, _ in pairs)
    for key, val in pairs:
        console.print(f"  [dim]{key.ljust(key_w)}[/dim]  {val}")

    if stats.numeric_stats:
        console.print()
        console.print(Rule("[dim]numeric[/dim]", style="dim", align="left"))
        console.print()

        table = RichTable(box=box.SIMPLE, header_style="dim", show_edge=False, padding=(0, 1))
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

    console.print()


def render_missing(schema: SchemaInfo) -> None:
    from dv.render.charts import _bar_unicode

    name = Path(schema.path).name
    console.print()
    console.print(Rule(f"[bold cyan]missing[/bold cyan]  [dim]{name}[/dim]", style="dim", align="left"))
    console.print()

    cols_with_missing = [c for c in schema.columns if c.missing > 0]
    if not cols_with_missing:
        console.print("  [dim]No missing values.[/dim]\n")
        return

    max_missing = max(c.missing for c in cols_with_missing)

    table = RichTable(box=box.SIMPLE, header_style="dim", show_edge=False, padding=(0, 1))
    table.add_column("column",  style="bold")
    table.add_column("missing", justify="right")
    table.add_column("pct",     justify="right", style="dim")
    table.add_column("chart")

    for col in schema.columns:
        if col.missing == 0:
            continue
        pct = col.missing / schema.row_count * 100 if schema.row_count else 0
        bar = _bar_unicode(col.missing, max_missing, 20)
        table.add_row(col.name, str(col.missing), f"{pct:.1f}%", bar)

    console.print(table)
    console.print()
