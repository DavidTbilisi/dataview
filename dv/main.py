from pathlib import Path
from typing import Optional, Annotated

import typer
from rich.console import Console

from dv.core.detect import make_datasource
from dv.core.query import run_query, run_table_query
from dv.core.schema import get_schema
from dv.core.stats import get_summary
from dv.core.config import load_config
from dv.render.table import render_table, render_pivot, render_top
from dv.render.summary import render_schema, render_summary, render_missing
from dv.render.charts import render_bar, render_sparkline, render_scatter, render_composition
from dv.render.histogram import render_histogram
from dv.render.timeline import render_timeline
from dv.render.heatmap import render_heatmap
from dv.render.tree import render_tree
from dv.render.export import export_markdown
from dv.render.calendar import render_calendar
from dv.render.gantt import render_gantt
from dv.render.box import render_box
from dv.render.diff import render_diff
from dv.render.time_views import (
    render_time_summary, render_streak, render_gaps, render_compare_periods,
)

app = typer.Typer(
    name="dv",
    help="Personal terminal dataview tool. Usage: dv <file> <command>",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()

_file: Path | None = None


def _ds():
    global _file
    if _file is None or not _file.exists():
        console.print(f"[red]File not found:[/red] {_file}")
        raise typer.Exit(1)
    return make_datasource(_file)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    file: Annotated[Optional[Path], typer.Argument(help="Input data file")] = None,
):
    """dv <file> <command> [options]"""
    global _file
    if file is not None:
        _file = file
    if ctx.invoked_subcommand is None and file is None:
        console.print(ctx.get_help())


# ─── Schema & inspection ──────────────────────────────────────────────────────

@app.command()
def schema():
    """Show column schema, types, missing %, and example values."""
    render_schema(get_schema(_ds()))


@app.command()
def head(n: int = typer.Option(10, "--lines", "-n", help="Number of rows")):
    """Show first N rows."""
    ds = _ds()
    render_table(run_table_query(ds, limit=n), title=f"{ds.path.name} — first {n} rows")


@app.command()
def summary():
    """Show summary statistics."""
    render_summary(get_summary(_ds()))


@app.command()
def describe():
    """Show numeric column statistics."""
    render_summary(get_summary(_ds()))


@app.command()
def missing():
    """Show missing value counts per column."""
    render_missing(get_schema(_ds()))


@app.command()
def table(
    limit: int = typer.Option(50, "--limit", "-l"),
    columns: Optional[str] = typer.Option(None, "--columns", "-c", help="Comma-separated columns"),
    where: Optional[str] = typer.Option(None, "--where", "-w"),
    sort: Optional[str] = typer.Option(None, "--sort", "-s"),
    desc: bool = typer.Option(False, "--desc"),
    truncate: Optional[int] = typer.Option(40, "--truncate", help="Truncate long text at N chars"),
):
    """Show data as a table with optional filters."""
    ds = _ds()
    cols = columns.split(",") if columns else None
    render_table(
        run_table_query(ds, limit=limit, columns=cols, where=where, sort=sort, desc=desc),
        title=ds.path.name,
        row_num=True,
        truncate=truncate,
    )


@app.command()
def query(sql: str = typer.Argument(..., help="SQL query (use 'data' as table name)")):
    """Run a SQL query against the file."""
    ds = _ds()
    render_table(run_query(ds, sql), title=f"Query: {ds.path.name}")


# ─── Aggregation ──────────────────────────────────────────────────────────────

@app.command(name="group-by")
def group_by(
    column: str = typer.Argument(..., help="Column to group by"),
    count: bool = typer.Option(False, "--count"),
    sum: Optional[str] = typer.Option(None, "--sum", help="Column to sum"),
    avg: Optional[str] = typer.Option(None, "--avg", help="Column to average"),
    bar: bool = typer.Option(False, "--bar", help="Also show bar chart"),
    limit: int = typer.Option(50, "--limit", "-l"),
):
    """Group by a column with optional aggregation."""
    ds = _ds()

    if sum:
        sql = f'SELECT "{column}", sum("{sum}") as total FROM data GROUP BY "{column}" ORDER BY total DESC LIMIT {limit}'
        agg_col = "total"
    elif avg:
        sql = f'SELECT "{column}", avg("{avg}") as avg_val FROM data GROUP BY "{column}" ORDER BY avg_val DESC LIMIT {limit}'
        agg_col = "avg_val"
    else:
        sql = f'SELECT "{column}", count(*) as count FROM data GROUP BY "{column}" ORDER BY count DESC LIMIT {limit}'
        agg_col = "count"

    result = run_query(ds, sql)
    render_table(result, title=f"group-by {column}")

    if bar and result.rows:
        render_bar([(row[column], row[agg_col]) for row in result.rows], title=column)


_MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@app.command()
def pivot(
    row_col: str = typer.Argument(..., help="Row dimension column"),
    col_col: str = typer.Argument(..., help="Column dimension (date col → months)"),
    sum_col: Optional[str] = typer.Option(None, "--sum", help="Column to sum"),
    count: bool = typer.Option(False, "--count"),
    avg_col: Optional[str] = typer.Option(None, "--avg", help="Column to average"),
):
    """Cross-tabulate two columns. Date columns are auto-bucketed by month."""
    ds = _ds()
    schema_info = get_schema(ds)

    col_type = next((c.inferred_type for c in schema_info.columns if c.name == col_col), "text")
    is_date  = col_type in ("date", "datetime")

    if sum_col:
        agg_expr  = f'sum("{sum_col}")'
        val_label = sum_col
        is_float  = True
    elif avg_col:
        agg_expr  = f'avg("{avg_col}")'
        val_label = avg_col
        is_float  = True
    else:
        agg_expr  = "count(*)"
        val_label = "count"
        is_float  = False

    if is_date:
        sql = f"""
            SELECT
                "{row_col}" AS _row,
                CAST(EXTRACT(month FROM "{col_col}") AS INTEGER) AS _sort,
                {agg_expr} AS _val
            FROM data
            WHERE "{col_col}" IS NOT NULL
            GROUP BY "{row_col}", CAST(EXTRACT(month FROM "{col_col}") AS INTEGER)
            ORDER BY "{row_col}", _sort
        """
        result   = run_query(ds, sql)
        sort_keys = sorted({r["_sort"] for r in result.rows})
        col_order = [_MONTH_ABBR[s - 1] for s in sort_keys]
        rows      = [{**r, "_col": _MONTH_ABBR[r["_sort"] - 1]} for r in result.rows]
    else:
        sql = f"""
            SELECT
                "{row_col}" AS _row,
                "{col_col}" AS _col,
                {agg_expr} AS _val
            FROM data
            WHERE "{col_col}" IS NOT NULL
            GROUP BY "{row_col}", "{col_col}"
            ORDER BY "{row_col}", "{col_col}"
        """
        result    = run_query(ds, sql)
        rows      = result.rows
        seen: list[str] = []
        for r in rows:
            if r["_col"] not in seen:
                seen.append(str(r["_col"]))
        col_order = seen

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
    limit: int = typer.Option(10, "--limit", "-l"),
):
    """Show top values ranked by a numeric sum, with share %."""
    ds = _ds()
    sql = f'SELECT "{column}", sum("{by}") as total FROM data GROUP BY "{column}" ORDER BY total DESC LIMIT {limit}'
    result = run_query(ds, sql)
    render_top(result.rows, column_name=column, value_name=by)


# ─── Charts ───────────────────────────────────────────────────────────────────

@app.command()
def bar(
    column: str = typer.Argument(..., help="Column to count or aggregate"),
    sum_col: Optional[str] = typer.Option(None, "--sum", help="Column to sum"),
    avg_col: Optional[str] = typer.Option(None, "--avg", help="Column to average"),
    limit: int = typer.Option(20, "--limit", "-l"),
    width: Optional[int] = typer.Option(None, "--width"),
):
    """Show a bar chart (count, sum, or average) for a column."""
    ds = _ds()
    if sum_col:
        sql     = f'SELECT "{column}", sum("{sum_col}") as val FROM data GROUP BY "{column}" ORDER BY val DESC LIMIT {limit}'
        agg_col = "val"
        title   = f"{sum_col} by {column}"
    elif avg_col:
        sql     = f'SELECT "{column}", avg("{avg_col}") as val FROM data GROUP BY "{column}" ORDER BY val DESC LIMIT {limit}'
        agg_col = "val"
        title   = f"avg {avg_col} by {column}"
    else:
        sql     = f'SELECT "{column}", count(*) as count FROM data GROUP BY "{column}" ORDER BY count DESC LIMIT {limit}'
        agg_col = "count"
        title   = column
    result = run_query(ds, sql)
    render_bar([(r[column], r[agg_col]) for r in result.rows], title=title, width=width)


@app.command()
def hist(
    column: str = typer.Argument(..., help="Numeric column"),
    bins: int = typer.Option(10, "--bins"),
    width: Optional[int] = typer.Option(None, "--width"),
):
    """Show a histogram of a numeric column."""
    ds = _ds()
    result = run_query(ds, f'SELECT "{column}" FROM data WHERE "{column}" IS NOT NULL')
    render_histogram([float(r[column]) for r in result.rows], title=column, bins=bins, width=width)


@app.command()
def scatter(
    x_col: str = typer.Argument(..., help="X-axis numeric column"),
    y_col: str = typer.Argument(..., help="Y-axis numeric column"),
    width: Optional[int] = typer.Option(None, "--width"),
    height: int = typer.Option(20, "--height"),
):
    """Show a scatter plot of two numeric columns."""
    ds = _ds()
    result = run_query(
        ds,
        f'SELECT "{x_col}", "{y_col}" FROM data WHERE "{x_col}" IS NOT NULL AND "{y_col}" IS NOT NULL',
    )
    points = [(float(r[x_col]), float(r[y_col])) for r in result.rows]
    render_scatter(points, x_label=x_col, y_label=y_col, width=width, height=height)


@app.command()
def spark(
    column: str = typer.Argument(..., help="Numeric column"),
    by: Optional[str] = typer.Option(None, "--by", help="Order-by column"),
):
    """Show a sparkline of a numeric column."""
    ds = _ds()
    order  = f'ORDER BY "{by}"' if by else ""
    result = run_query(ds, f'SELECT "{column}" FROM data WHERE "{column}" IS NOT NULL {order}')
    render_sparkline(
        [float(r[column]) for r in result.rows],
        title=f"{column} by {by}" if by else column,
    )


@app.command()
def composition(
    column: str = typer.Argument(..., help="Column for categories"),
    sum_col: Optional[str] = typer.Option(None, "--sum", help="Column to sum (default: count)"),
    limit: int = typer.Option(20, "--limit", "-l"),
    width: Optional[int] = typer.Option(None, "--width"),
):
    """Show percentage composition breakdown (pie chart replacement)."""
    ds = _ds()
    if sum_col:
        sql   = f'SELECT "{column}", sum("{sum_col}") as val FROM data GROUP BY "{column}" ORDER BY val DESC LIMIT {limit}'
        title = f"{sum_col} composition by {column}"
    else:
        sql   = f'SELECT "{column}", count(*) as val FROM data GROUP BY "{column}" ORDER BY val DESC LIMIT {limit}'
        title = f"composition by {column}"
    result = run_query(ds, sql)
    render_composition(
        [(r[column], float(r["val"])) for r in result.rows],
        title=title,
        width=width,
    )


@app.command()
def box(
    column: str = typer.Argument(..., help="Numeric column"),
    width: int = typer.Option(60, "--width"),
):
    """Show a box plot (min, q1, median, q3, max) for a numeric column."""
    ds     = _ds()
    result = run_query(ds, f'SELECT "{column}" FROM data WHERE "{column}" IS NOT NULL')
    render_box([float(r[column]) for r in result.rows], title=column, width=width)


@app.command()
def outliers(
    column: str = typer.Argument(..., help="Numeric column to scan"),
    limit: int = typer.Option(50, "--limit", "-l"),
):
    """Show outliers using IQR rule (values outside Q1 - 1.5·IQR or Q3 + 1.5·IQR)."""
    ds = _ds()
    sql = f"""
        WITH stats AS (
            SELECT
                quantile_cont("{column}", 0.25) AS q1,
                quantile_cont("{column}", 0.75) AS q3
            FROM data
        ),
        bounds AS (
            SELECT q1, q3, q3 - q1 AS iqr,
                   q1 - 1.5 * (q3 - q1) AS lower,
                   q3 + 1.5 * (q3 - q1) AS upper
            FROM stats
        )
        SELECT d.*, b.lower, b.upper
        FROM data d, bounds b
        WHERE d."{column}" < b.lower OR d."{column}" > b.upper
        ORDER BY d."{column}" DESC
        LIMIT {limit}
    """
    result = run_query(ds, sql)
    if not result.rows:
        console.print(f"\n  [dim]No outliers found in [bold]{column}[/bold] (IQR rule)[/dim]\n")
        return
    # Strip internal bound columns from display
    display_cols = [c for c in result.columns if c not in ("lower", "upper")]
    from dv.core.datasource import ResultView
    display = ResultView(columns=display_cols, rows=result.rows, metadata=result.metadata)
    render_table(display, title=f"OUTLIERS: {column}")
    console.print(f"  [dim]Rule: outside Q1 − 1.5·IQR or Q3 + 1.5·IQR[/dim]\n")


# ─── Matrix / multi-dim ───────────────────────────────────────────────────────

@app.command()
def heatmap(
    row_col: str = typer.Argument(..., help="Row dimension column"),
    col_col: str = typer.Argument(..., help="Column dimension column"),
):
    """Show a heatmap of two categorical columns."""
    ds = _ds()
    result = run_query(ds, f'SELECT "{row_col}", "{col_col}" FROM data')
    render_heatmap(result.rows, row_col=row_col, col_col=col_col, title=f"{row_col} × {col_col}")


@app.command()
def timeline(
    start: str = typer.Option(..., "--start", help="Start date column"),
    end: str = typer.Option(..., "--end", help="End date column"),
    label: str = typer.Option(..., "--label", help="Label column"),
    width: int = typer.Option(60, "--width"),
):
    """Show a timeline chart."""
    ds = _ds()
    result = run_query(ds, f'SELECT "{label}", "{start}", "{end}" FROM data ORDER BY "{start}"')
    render_timeline(result.rows, start_col=start, end_col=end, label_col=label, width=width)


@app.command()
def gantt(
    start: str = typer.Option(..., "--start", help="Start date column"),
    end: str = typer.Option(..., "--end", help="End date column"),
    label: str = typer.Option(..., "--label", help="Label column"),
    status: Optional[str] = typer.Option(None, "--status", help="Status column"),
    progress_col: Optional[str] = typer.Option(None, "--progress", help="Progress (0-100) column"),
    width: int = typer.Option(40, "--width"),
):
    """Show a Gantt chart with status-based bar styling."""
    ds = _ds()
    cols = [label, start, end]
    if status:
        cols.append(status)
    if progress_col:
        cols.append(progress_col)
    col_expr = ", ".join(f'"{c}"' for c in cols)
    result = run_query(ds, f"SELECT {col_expr} FROM data ORDER BY \"{start}\"")
    render_gantt(
        result.rows,
        start_col=start,
        end_col=end,
        label_col=label,
        status_col=status,
        progress_col=progress_col,
        width=width,
    )


@app.command()
def tree(
    path: str = typer.Option(..., "--path", help="Slash-separated column names for hierarchy"),
):
    """Show data as a tree using hierarchical columns."""
    ds = _ds()
    path_cols = path.split("/")
    col_expr  = ", ".join(f'"{c}"' for c in path_cols)
    render_tree(run_query(ds, f"SELECT {col_expr} FROM data").rows, path_cols=path_cols)


@app.command()
def calendar(
    date_col: str = typer.Option(..., "--date", help="Date column"),
    value_col: Optional[str] = typer.Option(None, "--value", help="Value column (default: count)"),
):
    """Show a calendar heatmap (weekday × month grid)."""
    ds     = _ds()
    cols   = f'"{date_col}"' + (f', "{value_col}"' if value_col else "")
    result = run_query(ds, f"SELECT {cols} FROM data WHERE \"{date_col}\" IS NOT NULL")
    render_calendar(result.rows, date_col=date_col, value_col=value_col,
                    title=f"{value_col or 'activity'} calendar")


# ─── Time commands ────────────────────────────────────────────────────────────

@app.command(name="time-summary")
def time_summary(
    date_col: str = typer.Option(..., "--date", help="Date column"),
):
    """Show time range, active days, and breakdown by month and weekday."""
    ds     = _ds()
    result = run_query(ds, f'SELECT "{date_col}" FROM data WHERE "{date_col}" IS NOT NULL')
    render_time_summary(result.rows, date_col=date_col)


@app.command(name="time")
def time_cmd(
    date_col: str = typer.Option(..., "--date", help="Date column"),
    by: str = typer.Option("month", "--by", help="Bucket: day|week|month|year|hour|weekday"),
    sum_col: Optional[str] = typer.Option(None, "--sum", help="Column to sum"),
    avg_col: Optional[str] = typer.Option(None, "--avg", help="Column to average"),
    limit: int = typer.Option(100, "--limit", "-l"),
):
    """Aggregate data by time bucket (day, week, month, year, hour, weekday)."""
    ds = _ds()

    if by == "month":
        period_expr = f"strftime(\"{date_col}\"::DATE, '%Y-%m')"
    elif by == "year":
        period_expr = f"CAST(EXTRACT(year FROM \"{date_col}\") AS INTEGER)"
    elif by == "day":
        period_expr = f"\"{date_col}\"::DATE"
    elif by == "week":
        period_expr = f"strftime(\"{date_col}\"::DATE, '%Y-W%W')"
    elif by == "hour":
        period_expr = f"CAST(EXTRACT(hour FROM \"{date_col}\") AS INTEGER)"
    elif by == "weekday":
        period_expr = f"CAST(EXTRACT(dow FROM \"{date_col}\") AS INTEGER)"
    else:
        console.print(f"[red]Unknown bucket:[/red] {by}. Use: day|week|month|year|hour|weekday")
        raise typer.Exit(1)

    if sum_col:
        agg     = f'sum("{sum_col}") as value'
        val_col = "value"
    elif avg_col:
        agg     = f'avg("{avg_col}") as value'
        val_col = "value"
    else:
        agg     = "count(*) as value"
        val_col = "value"

    sql = f"""
        SELECT {period_expr} AS period, {agg}
        FROM data
        WHERE "{date_col}" IS NOT NULL
        GROUP BY {period_expr}
        ORDER BY {period_expr}
        LIMIT {limit}
    """
    result = run_query(ds, sql)

    # For weekday, replace 0-6 with names
    rows = result.rows
    if by == "weekday":
        wd_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        rows = [{**r, "period": wd_names[int(r["period"])] if r["period"] is not None else "?"} for r in rows]

    agg_col_name = sum_col or avg_col or "count"
    rows = [{**r, "period": str(r["period"])} for r in rows]
    render_bar(
        [(r["period"], float(r[val_col]) if r[val_col] is not None else 0) for r in rows],
        title=f"{agg_col_name} by {by}",
    )


@app.command(name="by-hour")
def by_hour(
    date_col: str = typer.Option(..., "--date", help="Column with datetime/hour information"),
    sum_col: Optional[str] = typer.Option(None, "--sum"),
):
    """Show activity distribution by hour of day (00–23)."""
    ds = _ds()
    if sum_col:
        agg = f'sum("{sum_col}") as value'
    else:
        agg = "count(*) as value"
    sql = f"""
        SELECT CAST(EXTRACT(hour FROM "{date_col}") AS INTEGER) AS hour, {agg}
        FROM data
        WHERE "{date_col}" IS NOT NULL
        GROUP BY hour
        ORDER BY hour
    """
    result = run_query(ds, sql)
    # Fill missing hours with 0
    hour_map = {int(r["hour"]): float(r["value"]) for r in result.rows}
    rows_full = [(f"{h:02d}", hour_map.get(h, 0)) for h in range(24)]
    render_bar(rows_full, title=f"{sum_col or 'events'} by hour")


@app.command()
def streak(
    date_col: str = typer.Option(..., "--date", help="Date column"),
    where: Optional[str] = typer.Option(None, "--where", help="Optional WHERE filter"),
):
    """Show streak analysis: current streak, best streak, consistency."""
    ds    = _ds()
    cond  = f' WHERE "{date_col}" IS NOT NULL'
    if where:
        cond += f" AND ({where})"
    result = run_query(ds, f'SELECT "{date_col}" FROM data{cond} ORDER BY "{date_col}"')
    render_streak(result.rows, date_col=date_col)


@app.command()
def gaps(
    date_col: str = typer.Option(..., "--date", help="Date column"),
):
    """Show gaps between consecutive events."""
    ds     = _ds()
    result = run_query(ds, f'SELECT "{date_col}" FROM data WHERE "{date_col}" IS NOT NULL ORDER BY "{date_col}"')
    render_gaps(result.rows, date_col=date_col)


@app.command(name="compare-periods")
def compare_periods(
    date_col: str = typer.Option(..., "--date", help="Date column"),
    value_col: str = typer.Option(..., "--value", help="Numeric value column"),
    period: str = typer.Option("month", "--period", help="day|week|month|year"),
):
    """Show period-over-period comparison with % change."""
    ds = _ds()
    if period == "month":
        p_expr = f"strftime(\"{date_col}\"::DATE, '%Y-%m')"
    elif period == "year":
        p_expr = f"CAST(EXTRACT(year FROM \"{date_col}\") AS INTEGER)"
    elif period == "week":
        p_expr = f"strftime(\"{date_col}\"::DATE, '%Y-W%W')"
    else:
        p_expr = f"\"{date_col}\"::DATE"

    sql = f"""
        SELECT {p_expr} AS period, sum("{value_col}") AS total
        FROM data
        WHERE "{date_col}" IS NOT NULL
        GROUP BY {p_expr}
        ORDER BY {p_expr}
    """
    result = run_query(ds, sql)
    rows   = [{"period": str(r["period"]), "total": r["total"]} for r in result.rows]
    render_compare_periods(rows, period_col="period", value_col="total",
                           title=f"{value_col} by {period}")


# ─── Diff ─────────────────────────────────────────────────────────────────────

@app.command()
def diff(
    other: Path = typer.Argument(..., help="Second file to compare against"),
    key: str = typer.Option(..., "--key", help="Key column for row matching"),
):
    """Compare this file against another file row by row."""
    ds_a = _ds()
    if not other.exists():
        console.print(f"[red]File not found:[/red] {other}")
        raise typer.Exit(1)
    ds_b = make_datasource(other)

    result_a = run_query(ds_a, "SELECT * FROM data")
    result_b = run_query(ds_b, "SELECT * FROM data")
    cols = result_a.columns
    render_diff(
        result_a.rows,
        result_b.rows,
        key=key,
        columns=cols,
        title=f"DIFF: {ds_a.path.name} → {other.name}",
    )


# ─── Export & report ──────────────────────────────────────────────────────────

@app.command(name="export-md")
def export_md(output: Path = typer.Argument(..., help="Output markdown file")):
    """Export a markdown report of the file."""
    ds          = _ds()
    schema_info = get_schema(ds)
    stats       = get_summary(ds)

    chart_rows = []
    for col in schema_info.columns:
        if col.inferred_type == "text" and col.unique <= 30:
            result = run_query(
                ds,
                f'SELECT "{col.name}", count(*) as count FROM data GROUP BY "{col.name}" ORDER BY count DESC LIMIT 20',
            )
            chart_rows.append((col.name, [(r[col.name], r["count"]) for r in result.rows]))
            break

    export_markdown(output, schema_info, stats, chart_rows or None)
    console.print(f"[green]✓[/green] {output}")


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
                f'SELECT "{col.name}", count(*) as count FROM data GROUP BY "{col.name}" ORDER BY count DESC LIMIT 15',
            )
            render_bar(
                [(r[col.name], r["count"]) for r in result.rows],
                title=col.name,
            )
            break

    # First numeric column histogram
    for col in schema_info.columns:
        if col.inferred_type in ("integer", "float"):
            result = run_query(ds, f'SELECT "{col.name}" FROM data WHERE "{col.name}" IS NOT NULL')
            render_histogram(
                [float(r[col.name]) for r in result.rows],
                title=col.name,
                bins=8,
            )
            break

    # Missing values (if any)
    if stats.missing_total:
        render_missing(schema_info)
