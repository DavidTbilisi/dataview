"""SQL construction helpers.

Identifiers (column names) cannot be parameterized in DuckDB, so they are
quoted with `ident()`. Values always go through `?` placeholders instead of
being interpolated, so data containing apostrophes is handled correctly.
"""

from dv.core.errors import DvError

_BUCKETS = ("day", "week", "month", "year", "hour", "weekday")


def ident(name: str) -> str:
    """Quote an identifier for safe interpolation into SQL."""
    return '"' + str(name).replace('"', '""') + '"'


def lit(value) -> str:
    """Render a Python value as a SQL literal, escaping quotes.

    Preferred over interpolating a value into an f-string: this handles data
    containing apostrophes and leaves no way to break out of the literal.
    Use `run_query(..., params=[...])` instead where the query shape allows it.
    """
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def quote_path(path) -> str:
    """Quote a file path as a SQL string literal."""
    return "'" + str(path).replace("'", "''") + "'"


def period_expr(date_col: str, by: str) -> str:
    """SQL expression bucketing a date column into the given period."""
    col = ident(date_col)
    if by == "month":
        return f"strftime({col}::DATE, '%Y-%m')"
    if by == "year":
        return f"strftime({col}::DATE, '%Y')"
    if by == "week":
        return f"strftime({col}::DATE, '%Y-W%W')"
    if by == "day":
        return f"{col}::DATE"
    if by == "hour":
        return f"CAST(EXTRACT(hour FROM {col}) AS INTEGER)"
    if by == "weekday":
        return f"CAST(EXTRACT(dow FROM {col}) AS INTEGER)"
    raise DvError(
        f"Unknown time bucket: {by!r}",
        hint=f"Use one of: {', '.join(_BUCKETS)}",
    )


def order_by_agg(agg_col: str, group_col: str, desc: bool = True) -> str:
    """ORDER BY an aggregate, with the grouped column breaking ties.

    Without a tiebreaker DuckDB's parallel hash aggregate returns equal-valued
    groups in a different order run to run. Under a LIMIT that changes *which*
    rows appear, not just their order, so two runs of the same command over an
    unchanged file can disagree about the top 10.
    """
    return f"ORDER BY {ident(agg_col)} {'DESC' if desc else 'ASC'}, {ident(group_col)}"


def order_by_row(sort_col: str, desc: bool = True) -> str:
    """ORDER BY a column of the raw rows, with insertion order breaking ties.

    `rowid` is the table's physical order, so tied rows come back in file
    order. Only valid against the materialized table - the streamed commands
    (head, table, query) read a view, which has no rowid.
    """
    return f"ORDER BY {ident(sort_col)} {'DESC' if desc else 'ASC'}, rowid"


def agg_expr(
    sum_col: str | None,
    avg_col: str | None,
    alias: str | None = None,
) -> tuple[str, str, str]:
    """Return (sql_expression, result_column, label) for a sum/avg/count aggregation.

    With no `alias`, the result column is named for the aggregation — `total`,
    `avg`, or `count` — which reads better as a table header than a generic name.
    """
    if sum_col:
        name = alias or "total"
        return f"sum({ident(sum_col)}) AS {ident(name)}", name, sum_col
    if avg_col:
        name = alias or "avg"
        return f"avg({ident(avg_col)}) AS {ident(name)}", name, avg_col
    name = alias or "count"
    return f"count(*) AS {ident(name)}", name, "count"
