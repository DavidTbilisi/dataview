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
    render_weekmap, render_rolling, render_cumulative,
    render_duration_summary, render_before_after,
    render_countdown, render_sessions,
)
from dv.render.money import (
    render_money_summary, render_expenses_by, render_income_expense,
    render_budget, render_burn_rate, render_savings_rate,
    render_subscriptions, render_money_report,
    render_drill, render_spend_by_weekday, render_remaining,
    render_note_analysis, render_forecast,
)
from dv.render.teacher import (
    render_teacher_summary, render_gradebook, render_at_risk,
    render_score_distribution, render_missing_work,
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


# ─── Time (additional) ────────────────────────────────────────────────────────

@app.command()
def weekmap(
    date_col:  str = typer.Option(..., "--date",  help="Date column"),
    value_col: Optional[str] = typer.Option(None, "--value", help="Value column (default: count)"),
):
    """Show a week × weekday grid heatmap."""
    ds     = _ds()
    cols   = f'"{date_col}"' + (f', "{value_col}"' if value_col else "")
    result = run_query(ds, f"SELECT {cols} FROM data WHERE \"{date_col}\" IS NOT NULL")
    render_weekmap(result.rows, date_col=date_col, value_col=value_col,
                   title=f"{value_col or 'activity'} weekmap")


@app.command()
def rolling(
    date_col:  str = typer.Option(..., "--date",  help="Date column"),
    value_col: str = typer.Option(..., "--value", help="Numeric value column"),
    by:        str = typer.Option("month", "--by", help="day|week|month|year"),
    window:    int = typer.Option(3,   "--window", help="Rolling window size"),
):
    """Show values with rolling average overlay."""
    ds = _ds()
    if by == "month":
        p_expr = f"strftime(\"{date_col}\"::DATE, '%Y-%m')"
    elif by == "year":
        p_expr = f"CAST(EXTRACT(year FROM \"{date_col}\") AS INTEGER)"
    elif by == "week":
        p_expr = f"strftime(\"{date_col}\"::DATE, '%Y-W%W')"
    else:
        p_expr = f"\"{date_col}\"::DATE"
    sql = f"""
        SELECT {p_expr} AS period, sum("{value_col}") AS total
        FROM data WHERE "{date_col}" IS NOT NULL
        GROUP BY {p_expr} ORDER BY {p_expr}
    """
    result = run_query(ds, sql)
    items  = [(str(r["period"]), float(r["total"])) for r in result.rows]
    render_rolling(items, window=window, title=f"{value_col} by {by}")


@app.command()
def cumulative(
    date_col:  str = typer.Option(..., "--date",  help="Date column"),
    value_col: str = typer.Option(..., "--value", help="Numeric value column"),
    by:        str = typer.Option("month", "--by", help="day|week|month|year"),
):
    """Show cumulative running total over time."""
    ds = _ds()
    if by == "month":
        p_expr = f"strftime(\"{date_col}\"::DATE, '%Y-%m')"
    elif by == "year":
        p_expr = f"CAST(EXTRACT(year FROM \"{date_col}\") AS INTEGER)"
    elif by == "week":
        p_expr = f"strftime(\"{date_col}\"::DATE, '%Y-W%W')"
    else:
        p_expr = f"\"{date_col}\"::DATE"
    sql = f"""
        SELECT {p_expr} AS period, sum("{value_col}") AS total
        FROM data WHERE "{date_col}" IS NOT NULL
        GROUP BY {p_expr} ORDER BY {p_expr}
    """
    result = run_query(ds, sql)
    items  = [(str(r["period"]), float(r["total"])) for r in result.rows]
    render_cumulative(items, title=f"cumulative {value_col}")


@app.command()
def duration(
    start: str = typer.Option(..., "--start", help="Start date column"),
    end:   str = typer.Option(..., "--end",   help="End date column"),
):
    """Show distribution of durations between two date columns."""
    ds     = _ds()
    result = run_query(ds, f'SELECT "{start}", "{end}" FROM data WHERE "{start}" IS NOT NULL AND "{end}" IS NOT NULL')
    render_duration_summary(result.rows, start_col=start, end_col=end)


@app.command(name="before-after")
def before_after(
    date_col:  str = typer.Option(..., "--date",   help="Date column"),
    value_col: str = typer.Option(..., "--value",  help="Numeric value column"),
    cutoff:    str = typer.Option(..., "--cutoff", help="Cutoff date (YYYY-MM-DD)"),
):
    """Compare stats before and after a cutoff date."""
    ds = _ds()
    r_before = run_query(ds, f'SELECT "{value_col}" FROM data WHERE "{date_col}" < \'{cutoff}\'')
    r_after  = run_query(ds, f'SELECT "{value_col}" FROM data WHERE "{date_col}" >= \'{cutoff}\'')
    render_before_after(r_before.rows, r_after.rows, value_col=value_col, cutoff_str=cutoff)


# ─── Money ────────────────────────────────────────────────────────────────────

def _has_col(schema_info, col_name: str) -> bool:
    return any(c.name == col_name for c in schema_info.columns)


@app.command(name="money-summary")
def money_summary(
    type_col:    str = typer.Option("type",    "--type",    help="Transaction type column"),
    amount_col:  str = typer.Option("amount",  "--amount",  help="Amount column"),
    date_col:    str = typer.Option("date",    "--date",    help="Date column"),
    income_val:  str = typer.Option("income",  "--income",  help="Value meaning income"),
    expense_val: str = typer.Option("expense", "--expense", help="Value meaning expense"),
):
    """Show money summary: income, expenses, savings rate."""
    ds          = _ds()
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)

    if has_type:
        r_inc = run_query(ds, f"""
            SELECT COALESCE(sum("{amount_col}"), 0) AS total
            FROM data WHERE "{type_col}" = '{income_val}'
        """)
        r_exp = run_query(ds, f"""
            SELECT COALESCE(sum("{amount_col}"), 0)  AS total,
                   count(*)                           AS cnt,
                   COALESCE(avg("{amount_col}"), 0)  AS avg_val,
                   COALESCE(max("{amount_col}"), 0)  AS max_val
            FROM data WHERE "{type_col}" = '{expense_val}'
        """)
        income   = float(r_inc.rows[0]["total"])
        expense  = float(r_exp.rows[0]["total"])
        tx_count = int(r_exp.rows[0]["cnt"])
        avg_exp  = float(r_exp.rows[0]["avg_val"])
        max_exp  = float(r_exp.rows[0]["max_val"])
    else:
        r = run_query(ds, f"""
            SELECT COALESCE(sum("{amount_col}"), 0)  AS total,
                   count(*)                           AS cnt,
                   COALESCE(avg("{amount_col}"), 0)  AS avg_val,
                   COALESCE(max("{amount_col}"), 0)  AS max_val
            FROM data WHERE "{amount_col}" IS NOT NULL
        """)
        income   = 0.0
        expense  = float(r.rows[0]["total"])
        tx_count = int(r.rows[0]["cnt"])
        avg_exp  = float(r.rows[0]["avg_val"])
        max_exp  = float(r.rows[0]["max_val"])

    r_dates = run_query(ds, f'SELECT min("{date_col}") AS mn, max("{date_col}") AS mx FROM data')
    mn_d, mx_d = r_dates.rows[0]["mn"], r_dates.rows[0]["mx"]
    date_range = (str(mn_d)[:10], str(mx_d)[:10]) if mn_d else None

    accounts: list[str] = []
    if _has_col(schema_info, "account"):
        r_acc = run_query(ds, "SELECT DISTINCT account FROM data WHERE account IS NOT NULL ORDER BY account")
        accounts = [str(r["account"]) for r in r_acc.rows]

    render_money_summary(income, expense, tx_count, avg_exp, max_exp, date_range, accounts or None)


@app.command(name="expenses-by")
def expenses_by(
    column:      str = typer.Argument(..., help="Column to group by"),
    type_col:    str = typer.Option("type",    "--type"),
    amount_col:  str = typer.Option("amount",  "--amount"),
    expense_val: str = typer.Option("expense", "--expense"),
    limit:       int = typer.Option(15, "--limit", "-l"),
):
    """Show expenses broken down by a column (bar chart with %)."""
    ds          = _ds()
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)
    where       = f'WHERE "{type_col}" = \'{expense_val}\'' if has_type else f'WHERE "{amount_col}" IS NOT NULL'
    sql         = f'SELECT "{column}", sum("{amount_col}") AS total FROM data {where} GROUP BY "{column}" ORDER BY total DESC LIMIT {limit}'
    result      = run_query(ds, sql)
    items       = [(str(r[column]), float(r["total"])) for r in result.rows]
    render_expenses_by(items, title=f"EXPENSES BY {column.upper()}")


@app.command(name="income-expense")
def income_expense_cmd(
    by:          str = typer.Option("month",   "--by",      help="day|week|month|year"),
    type_col:    str = typer.Option("type",    "--type"),
    amount_col:  str = typer.Option("amount",  "--amount"),
    date_col:    str = typer.Option("date",    "--date"),
    income_val:  str = typer.Option("income",  "--income"),
    expense_val: str = typer.Option("expense", "--expense"),
):
    """Show income vs expense by time period."""
    ds = _ds()
    if by == "month":
        p_expr = f"strftime(\"{date_col}\"::DATE, '%Y-%m')"
    elif by == "year":
        p_expr = f"CAST(EXTRACT(year FROM \"{date_col}\") AS INTEGER)"
    elif by == "week":
        p_expr = f"strftime(\"{date_col}\"::DATE, '%Y-W%W')"
    else:
        p_expr = f"\"{date_col}\"::DATE"
    sql = f"""
        SELECT {p_expr} AS period,
               sum(CASE WHEN "{type_col}" = '{income_val}'  THEN "{amount_col}" ELSE 0 END) AS income,
               sum(CASE WHEN "{type_col}" = '{expense_val}' THEN "{amount_col}" ELSE 0 END) AS expense
        FROM data WHERE "{date_col}" IS NOT NULL
        GROUP BY {p_expr} ORDER BY {p_expr}
    """
    result = run_query(ds, sql)
    rows   = [{"period": str(r["period"]), "income": r["income"], "expense": r["expense"]}
              for r in result.rows]
    render_income_expense(rows)


@app.command()
def largest(
    amount_col:  str = typer.Option("amount",  "--amount"),
    type_col:    str = typer.Option("type",    "--type"),
    expense_val: str = typer.Option("expense", "--expense"),
    limit:       int = typer.Option(10, "--limit", "-l"),
):
    """Show the largest transactions sorted by amount."""
    ds          = _ds()
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)
    where       = f'WHERE "{type_col}" = \'{expense_val}\'' if has_type else f'WHERE "{amount_col}" IS NOT NULL'
    result      = run_query(ds, f'SELECT * FROM data {where} ORDER BY "{amount_col}" DESC LIMIT {limit}')
    render_table(result, title=f"LARGEST TRANSACTIONS")


@app.command()
def budget(
    column:      str  = typer.Argument(..., help="Category column"),
    budget_file: Path = typer.Option(..., "--budget", help="YAML file with category budgets"),
    type_col:    str  = typer.Option("type",    "--type"),
    amount_col:  str  = typer.Option("amount",  "--amount"),
    expense_val: str  = typer.Option("expense", "--expense"),
):
    """Compare actual spending against a YAML budget file."""
    import yaml
    ds          = _ds()
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)
    where       = f'WHERE "{type_col}" = \'{expense_val}\'' if has_type else f'WHERE "{amount_col}" IS NOT NULL'
    sql         = f'SELECT "{column}", sum("{amount_col}") AS total FROM data {where} GROUP BY "{column}" ORDER BY total DESC'
    result      = run_query(ds, sql)
    items       = [(str(r[column]), float(r["total"])) for r in result.rows]
    with open(budget_file) as f:
        budget_dict = yaml.safe_load(f)
    render_budget(items, budget_dict)


@app.command(name="burn-rate")
def burn_rate(
    budget_amount: float        = typer.Option(..., "--budget", help="Monthly budget"),
    month:         str          = typer.Option("",  "--month",  help="Month as YYYY-MM (default: latest in data)"),
    type_col:      str          = typer.Option("type",    "--type"),
    amount_col:    str          = typer.Option("amount",  "--amount"),
    date_col:      str          = typer.Option("date",    "--date"),
    expense_val:   str          = typer.Option("expense", "--expense"),
):
    """Show spending pace vs budget for a month."""
    from datetime import date as _date
    from calendar import monthrange
    ds          = _ds()
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)

    if not month:
        r = run_query(ds, f'SELECT max("{date_col}") AS mx FROM data')
        month = str(r.rows[0]["mx"])[:7]

    year, mon  = int(month[:4]), int(month[5:7])
    days_total = monthrange(year, mon)[1]
    today      = _date.today()
    if today.year == year and today.month == mon:
        days_passed = today.day
    else:
        days_passed = days_total

    type_filter = f' AND "{type_col}" = \'{expense_val}\'' if has_type else ''
    r_spent = run_query(ds, f"""
        SELECT COALESCE(sum("{amount_col}"), 0) AS total FROM data
        WHERE strftime("{date_col}"::DATE, '%Y-%m') = '{month}'{type_filter}
    """)
    spent = float(r_spent.rows[0]["total"])

    month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    render_burn_rate(spent, budget_amount, days_passed, days_total,
                     f"{month_names[mon - 1]} {year}")


@app.command(name="savings-rate")
def savings_rate_cmd(
    by:          str = typer.Option("month",   "--by"),
    type_col:    str = typer.Option("type",    "--type"),
    amount_col:  str = typer.Option("amount",  "--amount"),
    date_col:    str = typer.Option("date",    "--date"),
    income_val:  str = typer.Option("income",  "--income"),
    expense_val: str = typer.Option("expense", "--expense"),
):
    """Show savings rate trend by time period."""
    ds = _ds()
    if by == "month":
        p_expr = f"strftime(\"{date_col}\"::DATE, '%Y-%m')"
    elif by == "year":
        p_expr = f"CAST(EXTRACT(year FROM \"{date_col}\") AS INTEGER)"
    elif by == "week":
        p_expr = f"strftime(\"{date_col}\"::DATE, '%Y-W%W')"
    else:
        p_expr = f"\"{date_col}\"::DATE"
    sql = f"""
        SELECT {p_expr} AS period,
               sum(CASE WHEN "{type_col}" = '{income_val}'  THEN "{amount_col}" ELSE 0 END) AS income,
               sum(CASE WHEN "{type_col}" = '{expense_val}' THEN "{amount_col}" ELSE 0 END) AS expense
        FROM data WHERE "{date_col}" IS NOT NULL
        GROUP BY {p_expr} ORDER BY {p_expr}
    """
    result = run_query(ds, sql)
    rows   = [{"period": str(r["period"]), "income": r["income"], "expense": r["expense"]}
              for r in result.rows]
    render_savings_rate(rows)


@app.command()
def subscriptions(
    type_col:    str = typer.Option("type",    "--type"),
    amount_col:  str = typer.Option("amount",  "--amount"),
    date_col:    str = typer.Option("date",    "--date"),
    note_col:    str = typer.Option("note",    "--note",    help="Column to group recurring by"),
    expense_val: str = typer.Option("expense", "--expense"),
    min_months:  int = typer.Option(2, "--min-months", help="Minimum months to count as recurring"),
):
    """Detect recurring payments (same name, similar amount, multiple months)."""
    ds          = _ds()
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)
    type_filter = f' AND "{type_col}" = \'{expense_val}\'' if has_type else ''
    sql = f"""
        WITH monthly AS (
            SELECT
                "{note_col}" AS name,
                strftime("{date_col}"::DATE, '%Y-%m') AS month,
                avg("{amount_col}") AS avg_amount
            FROM data
            WHERE "{note_col}" IS NOT NULL{type_filter}
            GROUP BY "{note_col}", strftime("{date_col}"::DATE, '%Y-%m')
        )
        SELECT name, count(DISTINCT month) AS months, avg(avg_amount) AS amount
        FROM monthly
        GROUP BY name
        HAVING count(DISTINCT month) >= {min_months}
        ORDER BY months DESC, amount DESC
    """
    result = run_query(ds, sql)
    items  = [{"name": r["name"], "amount": r["amount"], "months": r["months"]}
              for r in result.rows]
    render_subscriptions(items)


@app.command(name="money-report")
def money_report(
    month:        str           = typer.Option("",         "--month",    help="Month YYYY-MM (default: all)"),
    type_col:     str           = typer.Option("type",     "--type"),
    amount_col:   str           = typer.Option("amount",   "--amount"),
    date_col:     str           = typer.Option("date",     "--date"),
    category_col: str           = typer.Option("category", "--category"),
    income_val:   str           = typer.Option("income",   "--income"),
    expense_val:  str           = typer.Option("expense",  "--expense"),
    budget_file:  Optional[Path]= typer.Option(None,       "--budget"),
):
    """Full money report: summary, expenses by category, cashflow."""
    import yaml
    ds          = _ds()
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)

    month_filter     = f' AND strftime("{date_col}"::DATE, \'%Y-%m\') = \'{month}\'' if month else ''
    month_filter_pre = f' WHERE strftime("{date_col}"::DATE, \'%Y-%m\') = \'{month}\'' if month else ' WHERE 1=1'
    type_exp_filter  = f'{month_filter_pre} AND "{type_col}" = \'{expense_val}\'' if has_type else f'{month_filter_pre} AND "{amount_col}" IS NOT NULL'

    if has_type:
        r_inc = run_query(ds, f'SELECT COALESCE(sum("{amount_col}"), 0) AS total FROM data WHERE "{type_col}" = \'{income_val}\'{month_filter}')
        r_exp = run_query(ds, f'SELECT COALESCE(sum("{amount_col}"), 0) AS total FROM data WHERE "{type_col}" = \'{expense_val}\'{month_filter}')
        income  = float(r_inc.rows[0]["total"])
        expense = float(r_exp.rows[0]["total"])
    else:
        r = run_query(ds, f'SELECT COALESCE(sum("{amount_col}"), 0) AS total FROM data WHERE "{amount_col}" IS NOT NULL{month_filter}')
        income  = 0.0
        expense = float(r.rows[0]["total"])

    r_cat     = run_query(ds, f'SELECT "{category_col}", sum("{amount_col}") AS total FROM data{type_exp_filter} GROUP BY "{category_col}" ORDER BY total DESC LIMIT 15')
    exp_by_cat = [(str(r[category_col]), float(r["total"])) for r in r_cat.rows]

    r_dates   = run_query(ds, f'SELECT min("{date_col}") AS mn, max("{date_col}") AS mx FROM data')
    mn_d, mx_d = r_dates.rows[0]["mn"], r_dates.rows[0]["mx"]
    date_range = (str(mn_d)[:10], str(mx_d)[:10]) if mn_d else None

    r_large = run_query(ds, f'SELECT "{date_col}", "{category_col}", "{amount_col}" FROM data{type_exp_filter} ORDER BY "{amount_col}" DESC LIMIT 5')

    budget_dict: dict[str, float] | None = None
    if budget_file:
        with open(budget_file) as f:
            budget_dict = yaml.safe_load(f)

    render_money_report(income, expense, exp_by_cat, date_range,
                        r_large.rows, budget_dict, month_label=month)


# ── Time commands (new) ──────────────────────────────────────────────────────

@app.command()
def countdown(
    date_col:  str = typer.Option("deadline", "--date",  help="Column with deadline dates"),
    label_col: str = typer.Option("task",     "--label", help="Column with task/event labels"),
):
    """Show days until (or since) each deadline."""
    ds   = _ds()
    sql  = f'SELECT * FROM data ORDER BY "{date_col}"'
    rows = run_query(ds, sql).rows
    render_countdown(rows, date_col=date_col, label_col=label_col)


@app.command()
def sessions(
    start_col: str = typer.Option("start",    "--start",    help="Start datetime column"),
    end_col:   str = typer.Option("end",      "--end",      help="End datetime column"),
    label_col: str = typer.Option("activity", "--label",    help="Activity label column"),
    width:     int = typer.Option(48,         "--width",    help="Timeline width in chars"),
):
    """Multi-day intraday session timeline (24h ruler per day)."""
    ds   = _ds()
    sql  = f'SELECT * FROM data ORDER BY "{start_col}"'
    rows = run_query(ds, sql).rows
    render_sessions(rows, start_col=start_col, end_col=end_col, label_col=label_col, width=width)


# ── Money commands (new) ─────────────────────────────────────────────────────

@app.command()
def drill(
    category:      str = typer.Argument(...,         help="Category value to drill into"),
    category_col:  str = typer.Option("category",    "--category"),
    subcat_col:    str = typer.Option("subcategory", "--subcat"),
    amount_col:    str = typer.Option("amount",      "--amount"),
    date_col:      str = typer.Option("date",        "--date"),
    type_col:      str = typer.Option("type",        "--type"),
    expense_val:   str = typer.Option("expense",     "--expense"),
    n:             int = typer.Option(5,             "--n",       help="Top N largest transactions"),
):
    """Drill into a single category: subcategory breakdown + largest transactions."""
    ds          = _ds()
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)
    has_subcat  = _has_col(schema_info, subcat_col)

    type_filter = f' AND "{type_col}" = \'{expense_val}\'' if has_type else ''
    where       = f'WHERE "{category_col}" = \'{category}\'{type_filter}'

    r_stats  = run_query(ds, f'SELECT COUNT(*) AS cnt, SUM("{amount_col}") AS total, AVG("{amount_col}") AS avg FROM data {where}')
    stats    = r_stats.rows[0] if r_stats.rows else {}
    total    = float(stats.get("total") or 0)
    tx_count = int(stats.get("cnt") or 0)
    avg      = float(stats.get("avg") or 0)

    subcats: list[tuple[str, float]] = []
    if has_subcat:
        r_sub  = run_query(ds, f'SELECT "{subcat_col}", SUM("{amount_col}") AS t FROM data {where} GROUP BY "{subcat_col}" ORDER BY t DESC')
        subcats = [(str(r[subcat_col]), float(r["t"])) for r in r_sub.rows]

    r_large  = run_query(ds, f'SELECT "{date_col}", "{subcat_col if has_subcat else category_col}", "{amount_col}" FROM data {where} ORDER BY "{amount_col}" DESC LIMIT {n}')
    render_drill(category, total, tx_count, avg, subcats, r_large.rows)


@app.command(name="spend-by-weekday")
def spend_by_weekday(
    date_col:    str = typer.Option("date",    "--date"),
    amount_col:  str = typer.Option("amount",  "--amount"),
    type_col:    str = typer.Option("type",    "--type"),
    expense_val: str = typer.Option("expense", "--expense"),
    mode:        str = typer.Option("total",   "--mode",   help="total or avg"),
):
    """Average or total spending by day of week (Mon–Sun)."""
    ds          = _ds()
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)
    type_filter = f' AND "{type_col}" = \'{expense_val}\'' if has_type else ''

    agg = f'SUM("{amount_col}")' if mode == "total" else f'AVG("{amount_col}")'
    sql = f"""
        SELECT dayname("{date_col}"::DATE) AS weekday,
               dayofweek("{date_col}"::DATE) AS dow,
               {agg} AS val
        FROM data
        WHERE "{amount_col}" IS NOT NULL{type_filter}
        GROUP BY weekday, dow
        ORDER BY dow
    """
    result = run_query(ds, sql)
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_abbr  = {"Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed", "Thursday": "Thu",
                 "Friday": "Fri", "Saturday": "Sat", "Sunday": "Sun"}
    row_map   = {r["weekday"]: float(r["val"] or 0) for r in result.rows}
    items     = [(day_abbr.get(d, d[:3]), row_map.get(d, 0.0)) for d in day_order if d in row_map]
    title     = f"SPENDING BY WEEKDAY ({mode})"
    render_spend_by_weekday(items, title=title)


@app.command()
def remaining(
    budget:      float = typer.Option(...,       "--budget", help="Total budget for the month"),
    month:       str   = typer.Option("",        "--month",  help="Month YYYY-MM (default: current)"),
    date_col:    str   = typer.Option("date",    "--date"),
    amount_col:  str   = typer.Option("amount",  "--amount"),
    type_col:    str   = typer.Option("type",    "--type"),
    expense_val: str   = typer.Option("expense", "--expense"),
):
    """Budget remaining and safe daily spend."""
    from calendar import monthrange
    from datetime import date

    ds          = _ds()
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)

    if not month:
        month = date.today().strftime("%Y-%m")

    type_filter = f' AND "{type_col}" = \'{expense_val}\'' if has_type else ''
    sql = f"""
        SELECT COALESCE(SUM("{amount_col}"), 0) AS spent
        FROM data
        WHERE strftime("{date_col}"::DATE, '%Y-%m') = '{month}'{type_filter}
    """
    spent = float(run_query(ds, sql).rows[0]["spent"])

    y, m     = int(month[:4]), int(month[5:7])
    days_total  = monthrange(y, m)[1]
    today       = date.today()
    if today.year == y and today.month == m:
        days_passed = today.day
    else:
        days_passed = days_total

    render_remaining(spent, budget, days_passed, days_total, month_label=month)


@app.command(name="note-analysis")
def note_analysis(
    note_col:    str = typer.Option("note",    "--note",    help="Merchant/note column"),
    amount_col:  str = typer.Option("amount",  "--amount"),
    type_col:    str = typer.Option("type",    "--type"),
    expense_val: str = typer.Option("expense", "--expense"),
    n:           int = typer.Option(20,        "--n",       help="Top N merchants"),
):
    """Group by merchant/note column: count, total, average."""
    ds          = _ds()
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)
    type_filter = f' AND "{type_col}" = \'{expense_val}\'' if has_type else ''

    sql = f"""
        SELECT "{note_col}" AS merchant,
               COUNT(*) AS count,
               SUM("{amount_col}") AS total,
               AVG("{amount_col}") AS avg
        FROM data
        WHERE "{amount_col}" IS NOT NULL{type_filter}
        GROUP BY "{note_col}"
        ORDER BY total DESC
        LIMIT {n}
    """
    rows  = run_query(ds, sql).rows
    items = [{"merchant": r["merchant"], "count": r["count"],
              "total": float(r["total"] or 0), "avg": float(r["avg"] or 0)}
             for r in rows]
    render_note_analysis(items)


@app.command()
def forecast(
    months_back: int = typer.Option(3,        "--history", help="Months of history to average"),
    months_fwd:  int = typer.Option(3,        "--forward", help="Months to project forward"),
    date_col:    str = typer.Option("date",   "--date"),
    amount_col:  str = typer.Option("amount", "--amount"),
    type_col:    str = typer.Option("type",   "--type"),
    income_val:  str = typer.Option("income", "--income"),
    expense_val: str = typer.Option("expense","--expense"),
):
    """Project future cashflow based on rolling average of recent months."""
    from datetime import date

    ds          = _ds()
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)

    if has_type:
        sql = f"""
            SELECT strftime("{date_col}"::DATE, '%Y-%m') AS period,
                   SUM(CASE WHEN "{type_col}" = '{income_val}'  THEN "{amount_col}" ELSE 0 END) AS income,
                   SUM(CASE WHEN "{type_col}" = '{expense_val}' THEN "{amount_col}" ELSE 0 END) AS expense
            FROM data
            GROUP BY period
            ORDER BY period DESC
            LIMIT {months_back}
        """
    else:
        sql = f"""
            SELECT strftime("{date_col}"::DATE, '%Y-%m') AS period,
                   0 AS income,
                   SUM("{amount_col}") AS expense
            FROM data
            GROUP BY period
            ORDER BY period DESC
            LIMIT {months_back}
        """

    hist_rows = run_query(ds, sql).rows
    if not hist_rows:
        console.print("[dim]No data[/dim]")
        return

    historical = [{"period": r["period"], "income": float(r["income"] or 0),
                   "expense": float(r["expense"] or 0)} for r in hist_rows]

    avg_inc = sum(r["income"] for r in historical) / len(historical)
    avg_exp = sum(r["expense"] for r in historical) / len(historical)

    # Project forward from next month
    today = date.today()
    y, m  = today.year, today.month
    projected = []
    for _ in range(months_fwd):
        m += 1
        if m > 12:
            m  = 1
            y += 1
        projected.append({"period": f"{y}-{m:02d}", "income": avg_inc, "expense": avg_exp})

    render_forecast(historical[::-1], projected)


# ── Teacher commands ──────────────────────────────────────────────────────────

@app.command(name="teacher-summary")
def teacher_summary(
    score_col:      str = typer.Option("score",      "--score"),
    max_score_col:  str = typer.Option("max_score",  "--max-score"),
    student_col:    str = typer.Option("student",    "--student"),
    assignment_col: str = typer.Option("assignment", "--assignment"),
    topic_col:      str = typer.Option("topic",      "--topic"),
):
    """Class overview: averages, pass rate, grade distribution, at-risk count."""
    ds   = _ds()
    rows = run_query(ds, "SELECT * FROM data").rows
    render_teacher_summary(rows, score_col=score_col, max_score_col=max_score_col,
                           student_col=student_col, assignment_col=assignment_col,
                           topic_col=topic_col)


@app.command()
def gradebook(
    score_col:      str = typer.Option("score",      "--score"),
    max_score_col:  str = typer.Option("max_score",  "--max-score"),
    student_col:    str = typer.Option("student",    "--student"),
    assignment_col: str = typer.Option("assignment", "--assignment"),
):
    """Pivot table: students × assignments with scores. Missing = '--'."""
    ds   = _ds()
    rows = run_query(ds, "SELECT * FROM data").rows
    render_gradebook(rows, score_col=score_col, max_score_col=max_score_col,
                     student_col=student_col, assignment_col=assignment_col)


@app.command(name="at-risk")
def at_risk(
    score_col:      str   = typer.Option("score",      "--score"),
    max_score_col:  str   = typer.Option("max_score",  "--max-score"),
    student_col:    str   = typer.Option("student",    "--student"),
    assignment_col: str   = typer.Option("assignment", "--assignment"),
):
    """Flag students below 70% average or with 2+ missing submissions."""
    ds   = _ds()
    rows = run_query(ds, "SELECT * FROM data").rows

    # Compute per-student avg and missing count
    all_assignments = sorted({r[assignment_col] for r in rows if r.get(assignment_col)})
    student_data: dict[str, dict[str, float | None]] = {}
    for r in rows:
        s  = r.get(student_col)
        a  = r.get(assignment_col)
        sc = r.get(score_col)
        mx = r.get(max_score_col, 100)
        if s and a:
            pct = float(sc) / float(mx) * 100 if sc is not None and mx else None
            student_data.setdefault(s, {})[a] = pct

    summary = []
    for student, scores in student_data.items():
        valid   = [v for v in scores.values() if v is not None]
        missing = sum(1 for a in all_assignments if scores.get(a) is None)
        avg     = sum(valid) / len(valid) if valid else 0.0
        summary.append({"student": student, "avg": avg, "missing": missing,
                         "assignments": len(valid)})

    render_at_risk(summary)


@app.command(name="score-distribution")
def score_distribution(
    assignment:     str = typer.Option("", "--assignment", "-a", help="Filter to one assignment (default: all)"),
    score_col:      str = typer.Option("score",      "--score"),
    max_score_col:  str = typer.Option("max_score",  "--max-score"),
    assignment_col: str = typer.Option("assignment", "--assignment-col"),
):
    """Histogram of scores grouped into grade bands (0-49, 50-59, …, 90-100)."""
    ds     = _ds()
    where  = f' WHERE "{assignment_col}" = \'{assignment}\'' if assignment else ''
    rows   = run_query(ds, f'SELECT "{score_col}", "{max_score_col}" FROM data{where}').rows
    scores = [float(r[score_col]) / float(r[max_score_col] or 100) * 100
              for r in rows if r.get(score_col) is not None]
    render_score_distribution(scores, assignment=assignment)


@app.command(name="missing-work")
def missing_work(
    student_col:    str = typer.Option("student",    "--student"),
    assignment_col: str = typer.Option("assignment", "--assignment"),
    score_col:      str = typer.Option("score",      "--score"),
    topic_col:      str = typer.Option("topic",      "--topic"),
):
    """List student × assignment combinations with no score (missing submissions)."""
    ds   = _ds()
    rows = run_query(ds, "SELECT * FROM data").rows

    all_assignments = sorted({r[assignment_col] for r in rows if r.get(assignment_col)})
    all_students    = sorted({r[student_col]    for r in rows if r.get(student_col)})
    submitted: set[tuple[str, str]] = {
        (r[student_col], r[assignment_col])
        for r in rows
        if r.get(student_col) and r.get(assignment_col) and r.get(score_col) is not None
    }

    missing_rows = []
    for student in all_students:
        for assignment in all_assignments:
            if (student, assignment) not in submitted:
                topic = next(
                    (r.get(topic_col, "") for r in rows if r.get(assignment_col) == assignment),
                    ""
                )
                missing_rows.append({"student": student, "assignment": assignment, "topic": topic})

    render_missing_work(missing_rows)
