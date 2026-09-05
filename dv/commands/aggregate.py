"""Grouping, cross-tabulation and ranking commands."""


import typer

from dv.app import (
    app,
    limit_or_default,
)
from dv.app import (
    ds as _ds,
)
from dv.core.query import require_columns, run_query
from dv.core.schema import get_schema
from dv.core.sql import agg_expr, ident
from dv.render.charts import render_bar
from dv.render.table import render_pivot, render_table, render_top

_MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _month_labels(year_months: list[str]) -> dict[str, str]:
    """Map '2026-06' keys to display labels.

    The year is shown only when the data spans more than one, so the common
    single-year case stays narrow while distinct years stay distinct.
    """
    years = {str(k).split("-")[0] for k in year_months}
    multi = len(years) > 1
    labels = {}
    for key in year_months:
        year, month = str(key).split("-")
        name = _MONTH_ABBR[int(month) - 1]
        labels[key] = f"{name} {year}" if multi else name
    return labels


@app.command(name="group-by")
def group_by(
    column: str = typer.Argument(..., help="Column to group by"),
    sum_col: str | None = typer.Option(None, "--sum", help="Column to sum"),
    avg_col: str | None = typer.Option(None, "--avg", help="Column to average"),
    count: bool = typer.Option(False, "--count", help="Count rows (the default)"),
    bar: bool = typer.Option(False, "--bar", help="Also show bar chart"),
    limit: int | None = typer.Option(None, "--limit", "-l"),
):
    """Group by a column with optional aggregation."""
    ds = _ds()
    limit = limit_or_default(limit, 50)
    require_columns(ds, column, sum_col, avg_col)

    c = ident(column)
    agg, agg_col, _ = agg_expr(sum_col, avg_col)
    sql = (f"SELECT {c}, {agg} FROM data GROUP BY {c} "
           f"ORDER BY {ident(agg_col)} DESC LIMIT {int(limit)}")

    result = run_query(ds, sql)
    render_table(result, title=f"group-by {column}")

    if bar and result.rows:
        render_bar([(row[column], row[agg_col]) for row in result.rows], title=column)


@app.command()
def pivot(
    row_col: str = typer.Argument(..., help="Row dimension column"),
    col_col: str = typer.Argument(..., help="Column dimension (date col becomes months)"),
    sum_col: str | None = typer.Option(None, "--sum", help="Column to sum"),
    avg_col: str | None = typer.Option(None, "--avg", help="Column to average"),
    count: bool = typer.Option(False, "--count", help="Count rows (the default)"),
):
    """Cross-tabulate two columns. Date columns are auto-bucketed by month."""
    ds = _ds()
    require_columns(ds, row_col, col_col, sum_col, avg_col)
    schema_info = get_schema(ds)

    col_type = next((c.inferred_type for c in schema_info.columns if c.name == col_col), "text")
    is_date  = col_type in ("date", "datetime")

    if sum_col:
        agg = f"sum({ident(sum_col)})"
        val_label, is_float = sum_col, True
    elif avg_col:
        agg = f"avg({ident(avg_col)})"
        val_label, is_float = avg_col, True
    else:
        agg = "count(*)"
        val_label, is_float = "count", False

    r_id, c_id = ident(row_col), ident(col_col)
    if is_date:
        # Bucket by year-month, not bare month: EXTRACT(month) alone merged
        # January 2025 into January 2026.
        bucket = f"strftime({c_id}::DATE, '%Y-%m')"
        sql = f"""
            SELECT {r_id} AS _row, {bucket} AS _sort, {agg} AS _val
            FROM data
            WHERE {c_id} IS NOT NULL
            GROUP BY {r_id}, {bucket}
            ORDER BY {r_id}, _sort
        """
        result = run_query(ds, sql)
        seen_keys = sorted({r["_sort"] for r in result.rows})
        labels = _month_labels(seen_keys)
        rows = [{**r, "_col": labels[r["_sort"]]} for r in result.rows]
        col_order = [labels[k] for k in seen_keys]
    else:
        sql = f"""
            SELECT {r_id} AS _row, {c_id} AS _col, {agg} AS _val
            FROM data
            WHERE {c_id} IS NOT NULL
            GROUP BY {r_id}, {c_id}
            ORDER BY {r_id}, {c_id}
        """
        result = run_query(ds, sql)
        rows = result.rows
        # Compare and store the same stringified value: comparing the raw value
        # against a list of strings never matched for non-string dimensions, so
        # every row appended a duplicate column.
        col_order = []
        for r in rows:
            label = str(r["_col"])
            if label not in col_order:
                col_order.append(label)

    col_label = "month" if is_date else col_col
    render_pivot(
        rows,
        row_label=row_col,
        col_order=col_order,
        title=f"{val_label} by {row_col} / {col_label}",
        is_float=is_float,
    )


@app.command()
def top(
    column: str = typer.Argument(..., help="Column to rank"),
    by: str = typer.Option(..., "--by", help="Numeric column to sum"),
    limit: int | None = typer.Option(None, "--limit", "-l"),
):
    """Show top values ranked by a numeric sum, with share %."""
    ds = _ds()
    limit = limit_or_default(limit, 10)
    require_columns(ds, column, by)
    sql = (f'SELECT "{column}", sum("{by}") as total FROM data '
           f'GROUP BY "{column}" ORDER BY total DESC LIMIT {limit}')
    result = run_query(ds, sql)
    render_top(result.rows, column_name=column, value_name=by)
