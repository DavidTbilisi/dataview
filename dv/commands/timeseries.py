"""Date- and time-series commands."""


import typer

from dv.app import (
    app,
    chart_width,
    limit_or_default,
)
from dv.app import (
    ds as _ds,
)
from dv.core.query import require_columns, run_query
from dv.core.sql import agg_expr, ident, lit, period_expr
from dv.render.charts import render_bar
from dv.render.time_views import (
    render_before_after,
    render_compare_periods,
    render_countdown,
    render_cumulative,
    render_duration_summary,
    render_gaps,
    render_rolling,
    render_sessions,
    render_streak,
    render_time_summary,
    render_weekmap,
)


@app.command(name="time-summary")
def time_summary(
    date_col: str = typer.Option(..., "--date", help="Date column"),
):
    """Show time range, active days, and breakdown by month and weekday."""
    ds     = _ds()
    require_columns(ds, date_col)
    result = run_query(ds, f'SELECT "{date_col}" FROM data WHERE "{date_col}" IS NOT NULL')
    render_time_summary(result.rows, date_col=date_col)


@app.command(name="time")
def time_cmd(
    date_col: str = typer.Option(..., "--date", help="Date column"),
    by: str = typer.Option("month", "--by", help="Bucket: day|week|month|year|hour|weekday"),
    sum_col: str | None = typer.Option(None, "--sum", help="Column to sum"),
    avg_col: str | None = typer.Option(None, "--avg", help="Column to average"),
    limit: int | None = typer.Option(None, "--limit", "-l"),
):
    """Aggregate data by time bucket (day, week, month, year, hour, weekday)."""
    ds = _ds()
    limit = limit_or_default(limit, 100)
    require_columns(ds, date_col, sum_col, avg_col)

    p_expr = period_expr(date_col, by)
    agg, val_col, _ = agg_expr(sum_col, avg_col, alias="value")

    sql = f"""
        SELECT {p_expr} AS period, {agg}
        FROM data
        WHERE {ident(date_col)} IS NOT NULL
        GROUP BY {p_expr}
        ORDER BY {p_expr}
        LIMIT {int(limit)}
    """
    result = run_query(ds, sql)

    # For weekday, replace 0-6 with names
    rows = result.rows
    if by == "weekday":
        wd_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        rows = [{**r, "period": wd_names[int(r["period"])] if r["period"] is not None else "?"}
                for r in rows]

    agg_col_name = sum_col or avg_col or "count"
    rows = [{**r, "period": str(r["period"])} for r in rows]
    render_bar(
        [(r["period"], float(r[val_col]) if r[val_col] is not None else 0) for r in rows],
        title=f"{agg_col_name} by {by}",
    )


@app.command(name="by-hour")
def by_hour(
    date_col: str = typer.Option(..., "--date", help="Column with datetime/hour information"),
    sum_col: str | None = typer.Option(None, "--sum"),
):
    """Show activity distribution by hour of day (00–23)."""
    ds = _ds()
    require_columns(ds, date_col, sum_col)
    agg = f'sum("{sum_col}") as value' if sum_col else "count(*) as value"
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
    where: str | None = typer.Option(None, "--where", help="Optional WHERE filter"),
):
    """Show streak analysis: current streak, best streak, consistency."""
    ds    = _ds()
    require_columns(ds, date_col)
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
    require_columns(ds, date_col)
    result = run_query(ds, f'SELECT "{date_col}" FROM data '
                           f'WHERE "{date_col}" IS NOT NULL ORDER BY "{date_col}"')
    render_gaps(result.rows, date_col=date_col)


@app.command(name="compare-periods")
def compare_periods(
    date_col: str = typer.Option(..., "--date", help="Date column"),
    value_col: str = typer.Option(..., "--value", help="Numeric value column"),
    period: str = typer.Option("month", "--period", help="day|week|month|year"),
):
    """Show period-over-period comparison with % change."""
    ds = _ds()
    require_columns(ds, date_col, value_col)
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


@app.command()
def weekmap(
    date_col:  str = typer.Option(..., "--date",  help="Date column"),
    value_col: str | None = typer.Option(None, "--value", help="Value column (default: count)"),
):
    """Show a week × weekday grid heatmap."""
    ds     = _ds()
    require_columns(ds, date_col, value_col)
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
    require_columns(ds, date_col, value_col)
    p_expr = period_expr(date_col, by)
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
    require_columns(ds, date_col, value_col)
    p_expr = period_expr(date_col, by)
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
    require_columns(ds, start, end)
    result = run_query(ds, f'SELECT "{start}", "{end}" FROM data '
                           f'WHERE "{start}" IS NOT NULL AND "{end}" IS NOT NULL')
    render_duration_summary(result.rows, start_col=start, end_col=end)


@app.command(name="before-after")
def before_after(
    date_col:  str = typer.Option(..., "--date",   help="Date column"),
    value_col: str = typer.Option(..., "--value",  help="Numeric value column"),
    cutoff:    str = typer.Option(..., "--cutoff", help="Cutoff date (YYYY-MM-DD)"),
):
    """Compare stats before and after a cutoff date."""
    ds = _ds()
    require_columns(ds, date_col, value_col)
    r_before = run_query(ds, f'SELECT "{value_col}" FROM data WHERE "{date_col}" < {lit(cutoff)}')
    r_after  = run_query(ds, f'SELECT "{value_col}" FROM data WHERE "{date_col}" >= {lit(cutoff)}')
    render_before_after(r_before.rows, r_after.rows, value_col=value_col, cutoff_str=cutoff)


@app.command()
def countdown(
    date_col:  str = typer.Option("deadline", "--date",  help="Column with deadline dates"),
    label_col: str = typer.Option("task",     "--label", help="Column with task/event labels"),
):
    """Show days until (or since) each deadline."""
    ds   = _ds()
    require_columns(ds, date_col, label_col)
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
    width = chart_width(width)
    require_columns(ds, start_col, end_col, label_col)
    sql  = f'SELECT * FROM data ORDER BY "{start_col}"'
    rows = run_query(ds, sql).rows
    render_sessions(rows, start_col=start_col, end_col=end_col, label_col=label_col, width=width)
