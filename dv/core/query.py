import difflib

import duckdb

from dv.core.datasource import DataSource, ResultView
from dv.core.errors import DvError
from dv.core.sql import ident, quote_path
from dv.render.theme import warn


def _get_read_expr(ds: DataSource) -> str:
    p = quote_path(ds.path)
    fmt = ds.format

    if fmt == "csv":
        return f"read_csv_auto({p})"
    elif fmt == "tsv":
        return f"read_csv_auto({p}, delim='\\t')"
    elif fmt == "json":
        return f"read_json_auto({p})"
    elif fmt == "ndjson":
        return f"read_ndjson_auto({p})"
    elif fmt == "parquet":
        return f"read_parquet({p})"
    elif fmt in ("sqlite", "duckdb"):
        raise ValueError(f"Use attach for {fmt} files")
    else:
        raise ValueError(f"Cannot generate read expression for format: {fmt}")


def get_connection(ds: DataSource) -> duckdb.DuckDBPyConnection:
    """Return the cached connection for this source, creating it on first use.

    The source is materialized into a real table rather than a view, so the
    input file is parsed once per process instead of once per query - which is
    what most commands want, since they run several queries over it.

    Commands that read once and bounded set `ds.stream` instead and get a view,
    so DuckDB pushes their LIMIT into the scan rather than parsing every row to
    show a handful. On a 91MB CSV that is the difference between 0.29s and
    0.04s for `head`.
    """
    if ds.connection is not None:
        return ds.connection

    conn = duckdb.connect()

    if ds.format in ("sqlite", "duckdb"):
        _attach_database(conn, ds)
    else:
        _load(conn, ds, f"SELECT * FROM {_get_read_expr(ds)}")
        _warn_if_unsplit(conn, ds)

    ds.connection = conn
    return conn


def _load(conn: duckdb.DuckDBPyConnection, ds: DataSource, select: str) -> None:
    """Register `select` as `data`, applying a global --where.

    Filtering here rather than in each command means every one of them - charts
    and reports included - honours --where without knowing it exists, and only
    the matching rows are ever materialized.
    """
    kind = "VIEW" if ds.stream else "TABLE"
    sql = f"CREATE {kind} {ident(ds.table_name)} AS {select}"
    if ds.where:
        sql += f" WHERE {ds.where}"
    try:
        conn.execute(sql)
    except duckdb.Error as e:
        if not ds.where:
            raise
        raise DvError(
            f"Could not apply --where {ds.where!r}",
            hint=str(e).strip().splitlines()[0],
        )


def _attach_database(conn: duckdb.DuckDBPyConnection, ds: DataSource) -> None:
    """Attach a SQLite/DuckDB file and expose its tables on the connection.

    Every table is registered as a view under its own name, so `query` can join
    across them. One of them also becomes `data` for the single-table commands:
    the one named by --table, or the only table if the file has just one.
    """
    conn.execute(f"ATTACH {quote_path(ds.path)} AS src (READ_ONLY)")
    # An attached database is a *catalog* named 'src'; its tables live in the
    # 'main' schema inside it. Filtering on table_schema found nothing, which
    # made every SQLite and DuckDB file look empty.
    names = [
        r[0]
        for r in conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_catalog = 'src' ORDER BY table_name"
        ).fetchall()
    ]
    if not names:
        raise DvError(f"No tables found in {ds.path.name}")

    for name in names:
        if name != ds.table_name:
            conn.execute(f"CREATE VIEW {ident(name)} AS SELECT * FROM src.{ident(name)}")

    chosen = ds.source_table
    if chosen is None:
        if len(names) > 1:
            raise DvError(
                f"{ds.path.name} has {len(names)} tables; pick one with --table",
                hint=f"Available: {', '.join(names)}",
            )
        chosen = names[0]
    elif chosen not in names:
        close = difflib.get_close_matches(chosen, names, n=1, cutoff=0.6)
        raise DvError(
            f"No table {chosen!r} in {ds.path.name}",
            hint=(f"Did you mean {close[0]!r}?" if close
                  else f"Available: {', '.join(names)}"),
        )

    _load(conn, ds, f"SELECT * FROM src.{ident(chosen)}")


_DELIMITERS = (",", "\t", ";", "|")


def _warn_if_unsplit(conn: duckdb.DuckDBPyConnection, ds: DataSource) -> None:
    """Warn when a delimited file did not actually split into columns.

    Rows with inconsistent field counts make DuckDB's sniffer give up on the
    delimiter and read each line as one value, so the sole column ends up named
    after the whole header line. Loading still succeeds, and silently reporting
    "1 column" on a ragged file is more misleading than a warning.
    """
    if ds.format not in ("csv", "tsv"):
        return
    cols = [
        r[0]
        for r in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ?",
            [ds.table_name],
        ).fetchall()
    ]
    if len(cols) == 1 and any(d in cols[0] for d in _DELIMITERS):
        warn(
            f"{ds.path.name} did not split into columns - read as a single "
            f"column named {cols[0]!r}.",
            hint="Rows with differing field counts stop the delimiter being detected.",
        )


def run_query(ds: DataSource, sql: str, params: list | None = None) -> ResultView:
    """Run SQL against the source. User values belong in `params`, not in `sql`."""
    conn = get_connection(ds)
    result = conn.execute(sql, params) if params else conn.execute(sql)
    columns = [desc[0] for desc in result.description]
    rows = [dict(zip(columns, row)) for row in result.fetchall()]
    return ResultView(columns=columns, rows=rows)


def run_query_capped(ds: DataSource, sql: str, limit: int) -> ResultView:
    """Run user SQL, materializing at most `limit` rows in Python.

    A bare `select * from data` over a large file used to build one dict per
    row before rendering any of them, which is unusable long before it is slow.
    Fetching limit+1 rows detects that there is more without reading it.
    """
    conn = get_connection(ds)
    result = conn.execute(sql)
    if result.description is None:      # a statement that returns no rows
        return ResultView(columns=[], rows=[])

    cols = [desc[0] for desc in result.description]
    fetched = result.fetchmany(limit + 1)
    truncated = len(fetched) > limit
    rows = [dict(zip(cols, row)) for row in fetched[:limit]]

    total = None
    if truncated:
        try:
            total = conn.execute(f"SELECT count(*) FROM ({sql}) AS _dv_count").fetchone()[0]
        except duckdb.Error:
            # Not every statement can be wrapped in a subquery; the row cap
            # still holds, we just cannot name the total.
            total = None

    return ResultView(
        columns=cols,
        rows=rows,
        metadata={"truncated": truncated, "total": total, "shown": len(rows)},
    )


def columns(ds: DataSource) -> list[str]:
    """Column names of the source table."""
    conn = get_connection(ds)
    return [
        r[0]
        for r in conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = ? ORDER BY ordinal_position",
            [ds.table_name],
        ).fetchall()
    ]


def require_columns(ds: DataSource, *names: str | None) -> None:
    """Raise a friendly DvError if any named column is missing."""
    available = columns(ds)
    lowered = {c.lower(): c for c in available}
    for name in names:
        if name is None or name in available:
            continue
        if name.lower() in lowered:
            continue
        close = difflib.get_close_matches(name, available, n=1, cutoff=0.6)
        hint = f"Did you mean {close[0]!r}?" if close else f"Available: {', '.join(available)}"
        raise DvError(f"Unknown column {name!r}", hint=hint)


def require_numeric(ds: DataSource, *names: str | None) -> None:
    """Raise a friendly DvError if any named column is not numeric."""
    require_columns(ds, *names)
    conn = get_connection(ds)
    types = dict(
        conn.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = ?",
            [ds.table_name],
        ).fetchall()
    )
    numeric = ("INT", "DEC", "DOUBLE", "FLOAT", "REAL", "NUMERIC", "HUGEINT")
    for name in names:
        if name is None:
            continue
        t = str(types.get(name, "")).upper()
        if not any(n in t for n in numeric):
            raise DvError(
                f"Column {name!r} is not numeric (type {t or 'unknown'})",
                hint="This command needs a numeric column.",
            )


def run_table_query(
    ds: DataSource,
    limit: int = 50,
    columns: list[str] | None = None,
    where: str | None = None,
    sort: str | None = None,
    desc: bool = False,
) -> ResultView:
    if columns:
        require_columns(ds, *columns)
        col_expr = ", ".join(ident(c) for c in columns)
    else:
        col_expr = "*"
    if sort:
        require_columns(ds, sort)
    sql = f"SELECT {col_expr} FROM {ident(ds.table_name)}"
    if where:
        sql += f" WHERE {where}"
    if sort:
        direction = "DESC" if desc else "ASC"
        sql += f" ORDER BY {ident(sort)} {direction}"
    sql += f" LIMIT {int(limit)}"
    return run_query(ds, sql)
