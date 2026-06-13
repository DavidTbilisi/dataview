import duckdb
from pathlib import Path

from dv.core.datasource import DataSource, ResultView
from dv.core.detect import detect_format


def _get_read_expr(ds: DataSource) -> str:
    p = str(ds.path)
    fmt = ds.format

    if fmt == "csv":
        return f"read_csv_auto('{p}')"
    elif fmt == "tsv":
        return f"read_csv_auto('{p}', delim='\\t')"
    elif fmt == "json":
        return f"read_json_auto('{p}')"
    elif fmt == "ndjson":
        return f"read_ndjson_auto('{p}')"
    elif fmt == "parquet":
        return f"read_parquet('{p}')"
    elif fmt in ("sqlite", "duckdb"):
        raise ValueError(f"Use attach for {fmt} files")
    else:
        raise ValueError(f"Cannot generate read expression for format: {fmt}")


def get_connection(ds: DataSource) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect()

    if ds.format in ("sqlite", "duckdb"):
        conn.execute(f"ATTACH '{ds.path}' AS src (READ_ONLY)")
        # register first table found as "data"
        tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'src'").fetchall()
        if not tables:
            raise ValueError("No tables found in database file")
        first_table = tables[0][0]
        conn.execute(f"CREATE VIEW {ds.table_name} AS SELECT * FROM src.{first_table}")
    else:
        read_expr = _get_read_expr(ds)
        conn.execute(f"CREATE VIEW {ds.table_name} AS SELECT * FROM {read_expr}")

    return conn


def run_query(ds: DataSource, sql: str) -> ResultView:
    conn = get_connection(ds)
    result = conn.execute(sql)
    columns = [desc[0] for desc in result.description]
    rows = [dict(zip(columns, row)) for row in result.fetchall()]
    return ResultView(columns=columns, rows=rows)


def run_table_query(
    ds: DataSource,
    limit: int = 50,
    columns: list[str] | None = None,
    where: str | None = None,
    sort: str | None = None,
    desc: bool = False,
) -> ResultView:
    col_expr = ", ".join(columns) if columns else "*"
    sql = f"SELECT {col_expr} FROM {ds.table_name}"
    if where:
        sql += f" WHERE {where}"
    if sort:
        direction = "DESC" if desc else "ASC"
        sql += f" ORDER BY {sort} {direction}"
    sql += f" LIMIT {limit}"
    return run_query(ds, sql)
