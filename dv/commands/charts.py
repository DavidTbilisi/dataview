"""Chart and diagram commands."""


import typer

from dv.app import (
    app,
    chart_width,
    limit_or_default,
)
from dv.app import (
    ds as _ds,
)
from dv.core.errors import DvError
from dv.core.query import require_columns, require_numeric, run_query
from dv.core.sql import ident
from dv.core.stats import (
    box_stats,
    cross_counts,
    daily_totals,
    numeric_bins,
    scatter_grid,
    spark_series,
)
from dv.render.box import render_box
from dv.render.calendar import render_calendar
from dv.render.charts import render_bar, render_composition, render_scatter, render_sparkline
from dv.render.gantt import render_gantt
from dv.render.heatmap import render_heatmap
from dv.render.histogram import render_histogram
from dv.render.table import render_table
from dv.render.theme import charset, console
from dv.render.timeline import render_timeline
from dv.render.tree import render_tree


@app.command()
def bar(
    column: str = typer.Argument(..., help="Column to count or aggregate"),
    sum_col: str | None = typer.Option(None, "--sum", help="Column to sum"),
    avg_col: str | None = typer.Option(None, "--avg", help="Column to average"),
    limit: int | None = typer.Option(None, "--limit", "-l"),
    width: int | None = typer.Option(None, "--width"),
):
    """Show a bar chart (count, sum, or average) for a column."""
    ds = _ds()
    limit = limit_or_default(limit, 20)
    width = chart_width(width)
    require_columns(ds, column, sum_col, avg_col)
    if sum_col:
        sql     = (f'SELECT "{column}", sum("{sum_col}") as val FROM data '
                   f'GROUP BY "{column}" ORDER BY val DESC LIMIT {limit}')
        agg_col = "val"
        title   = f"{sum_col} by {column}"
    elif avg_col:
        sql     = (f'SELECT "{column}", avg("{avg_col}") as val FROM data '
                   f'GROUP BY "{column}" ORDER BY val DESC LIMIT {limit}')
        agg_col = "val"
        title   = f"avg {avg_col} by {column}"
    else:
        sql     = (f'SELECT "{column}", count(*) as count FROM data '
                   f'GROUP BY "{column}" ORDER BY count DESC LIMIT {limit}')
        agg_col = "count"
        title   = column
    result = run_query(ds, sql)
    render_bar([(r[column], r[agg_col]) for r in result.rows], title=title, width=width)


@app.command()
def hist(
    column: str = typer.Argument(..., help="Numeric column"),
    bins: int = typer.Option(10, "--bins"),
    width: int | None = typer.Option(None, "--width"),
):
    """Show a histogram of a numeric column."""
    ds = _ds()
    width = chart_width(width)
    require_numeric(ds, column)
    render_histogram(numeric_bins(ds, column, bins), title=column, width=width)


@app.command()
def scatter(
    x_col: str = typer.Argument(..., help="X-axis numeric column"),
    y_col: str = typer.Argument(..., help="Y-axis numeric column"),
    width: int | None = typer.Option(None, "--width"),
    height: int = typer.Option(20, "--height"),
):
    """Show a scatter plot of two numeric columns."""
    ds = _ds()
    width = chart_width(width)
    require_numeric(ds, x_col, y_col)
    render_scatter(scatter_grid(ds, x_col, y_col),
                   x_label=x_col, y_label=y_col, width=width, height=height)


@app.command()
def spark(
    column: str = typer.Argument(..., help="Numeric column"),
    by: str | None = typer.Option(None, "--by", help="Order-by column"),
    width: int | None = typer.Option(None, "--width", help="Sparkline length in glyphs"),
):
    """Show a sparkline of a numeric column."""
    ds = _ds()
    require_numeric(ds, column)
    require_columns(ds, by)
    # A sparkline is one glyph wide per point, so ask for no more points than
    # fit on a line: without this a large column became a one-line wall of text.
    points = chart_width(width) or max(20, (console.width or 80) - 4)
    render_sparkline(
        spark_series(ds, column, order_by=by, points=points),
        title=f"{column} by {by}" if by else column,
    )


@app.command()
def composition(
    column: str = typer.Argument(..., help="Column for categories"),
    sum_col: str | None = typer.Option(None, "--sum", help="Column to sum (default: count)"),
    limit: int | None = typer.Option(None, "--limit", "-l"),
    width: int | None = typer.Option(None, "--width"),
):
    """Show percentage composition breakdown (pie chart replacement)."""
    ds = _ds()
    limit = limit_or_default(limit, 20)
    width = chart_width(width)
    require_columns(ds, column, sum_col)
    if sum_col:
        sql   = (f'SELECT "{column}", sum("{sum_col}") as val FROM data '
                 f'GROUP BY "{column}" ORDER BY val DESC LIMIT {limit}')
        title = f"{sum_col} composition by {column}"
    else:
        sql   = (f'SELECT "{column}", count(*) as val FROM data '
                 f'GROUP BY "{column}" ORDER BY val DESC LIMIT {limit}')
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
    width = chart_width(width)
    require_numeric(ds, column)
    render_box(box_stats(ds, column), title=column, width=width)


@app.command()
def outliers(
    column: str = typer.Argument(..., help="Numeric column to scan"),
    limit: int | None = typer.Option(None, "--limit", "-l"),
):
    """Show outliers using IQR rule (values outside Q1 - 1.5·IQR or Q3 + 1.5·IQR)."""
    ds = _ds()
    limit = limit_or_default(limit, 50)
    require_numeric(ds, column)
    c = ident(column)
    sql = f"""
        WITH stats AS (
            SELECT
                quantile_cont({c}, 0.25) AS q1,
                quantile_cont({c}, 0.75) AS q3
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
        WHERE d.{c} < b.lower OR d.{c} > b.upper
        -- Order by distance from the fence so a LIMIT keeps the most extreme
        -- outliers from BOTH tails, not just the largest values.
        ORDER BY greatest(b.lower - d.{c}, d.{c} - b.upper) DESC
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
    console.print("  [dim]Rule: outside Q1 - 1.5*IQR or Q3 + 1.5*IQR[/dim]\n")


@app.command()
def heatmap(
    row_col: str = typer.Argument(..., help="Row dimension column"),
    col_col: str = typer.Argument(..., help="Column dimension column"),
):
    """Show a heatmap of two categorical columns."""
    ds = _ds()
    require_columns(ds, row_col, col_col)
    render_heatmap(cross_counts(ds, row_col, col_col),
                   title=f"{row_col} {charset().times} {col_col}")


@app.command()
def timeline(
    start: str = typer.Option(..., "--start", help="Start date column"),
    end: str = typer.Option(..., "--end", help="End date column"),
    label: str = typer.Option(..., "--label", help="Label column"),
    width: int = typer.Option(60, "--width"),
):
    """Show a timeline chart."""
    ds = _ds()
    width = chart_width(width)
    require_columns(ds, start, end, label)
    result = run_query(ds, f'SELECT "{label}", "{start}", "{end}" FROM data ORDER BY "{start}"')
    render_timeline(result.rows, start_col=start, end_col=end, label_col=label, width=width)


@app.command()
def gantt(
    start: str = typer.Option(..., "--start", help="Start date column"),
    end: str = typer.Option(..., "--end", help="End date column"),
    label: str = typer.Option(..., "--label", help="Label column"),
    status: str | None = typer.Option(None, "--status", help="Status column"),
    progress_col: str | None = typer.Option(None, "--progress", help="Progress (0-100) column"),
    width: int = typer.Option(40, "--width"),
):
    """Show a Gantt chart with status-based bar styling."""
    ds = _ds()
    width = chart_width(width)
    require_columns(ds, start, end, label, status, progress_col)
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
    path_cols = [c.strip() for c in path.split("/") if c.strip()]
    if not path_cols:
        raise DvError("Empty --path", hint="Use --path col1/col2/col3")
    require_columns(ds, *path_cols)
    col_expr = ", ".join(ident(c) for c in path_cols)
    render_tree(run_query(ds, f"SELECT {col_expr} FROM data").rows, path_cols=path_cols)


@app.command()
def calendar(
    date_col: str = typer.Option(..., "--date", help="Date column"),
    value_col: str | None = typer.Option(None, "--value", help="Value column (default: count)"),
):
    """Show a calendar heatmap (weekday × month grid)."""
    ds     = _ds()
    require_columns(ds, date_col, value_col)
    render_calendar(daily_totals(ds, date_col, value_col),
                    title=f"{value_col or 'activity'} calendar")
