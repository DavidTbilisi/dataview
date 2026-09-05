import difflib

import duckdb

from dv.core.datasource import DataSource, ResultView
from dv.core.errors import DvError
from dv.core.sql import ident, quote_path


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
    input file is parsed once per process instead of once per query.
    """
    if ds.connection is not None:
        return ds.connection

    conn = duckdb.connect()
    tbl = ident(ds.table_name)

    if ds.format in ("sqlite", "duckdb"):
        conn.execute(f"ATTACH {quote_path(ds.path)} AS src (READ_ONLY)")
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'src'"
        ).fetchall()
        if not tables:
            raise DvError(f"No tables found in {ds.path.name}")
        first_table = tables[0][0]
        conn.execute(f"CREATE TABLE {tbl} AS SELECT * FROM src.{ident(first_table)}")
    else:
        conn.execute(f"CREATE TABLE {tbl} AS SELECT * FROM {_get_read_expr(ds)}")

    ds.connection = conn
    return conn


def run_query(ds: DataSource, sql: str, params: list | None = None) -> ResultView:
    """Run SQL against the source. User values belong in `params`, not in `sql`."""
    conn = get_connection(ds)
    result = conn.execute(sql, params) if params else conn.execute(sql)
    columns = [desc[0] for desc in result.description]
    rows = [dict(zip(columns, row)) for row in result.fetchall()]
    return ResultView(columns=columns, rows=rows)


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
