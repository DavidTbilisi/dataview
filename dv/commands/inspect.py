"""Schema, summary and raw-table inspection commands."""


import typer

from dv.app import (
    app,
    limit_or_default,
)
from dv.app import (
    ds as _ds,
)
from dv.core.query import run_query, run_query_capped, run_table_query
from dv.core.schema import get_schema
from dv.core.sql import order_by_agg
from dv.core.stats import get_summary, numeric_bins
from dv.render.charts import render_bar
from dv.render.histogram import render_histogram
from dv.render.summary import render_describe, render_missing, render_schema, render_summary
from dv.render.table import render_table
from dv.render.theme import charset


@app.command()
def schema():
    """Show column schema, types, missing %, and example values."""
    render_schema(get_schema(_ds()))


@app.command()
def head(n: int = typer.Option(10, "--lines", "-n", help="Number of rows")):
    """Show first N rows."""
    ds = _ds(stream=True)
    render_table(run_table_query(ds, limit=n),
                 title=f"{ds.path.name} {charset().emdash} first {n} rows")


@app.command()
def summary():
    """Show summary statistics."""
    render_summary(get_summary(_ds()))


@app.command()
def describe():
    """Show numeric column statistics only (count, min, max, mean, median, std)."""
    render_describe(get_summary(_ds()))


@app.command()
def missing():
    """Show missing value counts per column."""
    render_missing(get_schema(_ds()))


@app.command()
def table(
    limit: int | None = typer.Option(None, "--limit", "-l"),
    columns: str | None = typer.Option(None, "--columns", "-c", help="Comma-separated columns"),
    where: str | None = typer.Option(None, "--where", "-w"),
    sort: str | None = typer.Option(None, "--sort", "-s"),
    desc: bool = typer.Option(False, "--desc"),
    truncate: int | None = typer.Option(40, "--truncate", help="Truncate long text at N chars"),
):
    """Show data as a table with optional filters."""
    ds = _ds(stream=True)
    limit = limit_or_default(limit, 50)
    cols = columns.split(",") if columns else None
    render_table(
        run_table_query(ds, limit=limit, columns=cols, where=where, sort=sort, desc=desc),
        title=ds.path.name,
        row_num=True,
        truncate=truncate,
    )


@app.command()
def query(
    sql: str = typer.Argument(..., help="SQL query (use 'data' as table name)"),
    limit: int | None = typer.Option(None, "--limit", "-l",
                                        help="Maximum rows to render"),
    all_rows: bool = typer.Option(False, "--all",
                                  help="Render every row, however many"),
):
    """Run a SQL query against the file."""
    # A capped query reads once with a LIMIT DuckDB can push down; --all reads
    # every row anyway, so it wants the materialized table.
    ds = _ds(stream=not all_rows)
    if all_rows:
        result = run_query(ds, sql)
    else:
        result = run_query_capped(ds, sql, limit_or_default(limit, 200))
    render_table(result, title=f"Query: {ds.path.name}")


@app.command()
def report():
    """Show a full terminal report: summary, schema, top chart, histogram, missing."""
    ds          = _ds()
    schema_info = get_schema(ds)
    stats       = get_summary(ds)

    render_summary(stats)
    render_schema(schema_info)

    # Top categorical column bar
    for col in schema_info.columns:
        if col.inferred_type == "text" and 2 <= col.unique <= 25:
            result = run_query(
                ds,
                f'SELECT "{col.name}", count(*) as count FROM data '
                f'GROUP BY "{col.name}" {order_by_agg("count", col.name)} LIMIT 15',
            )
            render_bar(
                [(r[col.name], r["count"]) for r in result.rows],
                title=col.name,
            )
            break

    # First numeric column histogram
    for col in schema_info.columns:
        if col.inferred_type in ("integer", "float"):
            render_histogram(numeric_bins(ds, col.name, bins=8), title=col.name)
            break

    # Missing values (if any)
    if stats.missing_total:
        render_missing(schema_info)
