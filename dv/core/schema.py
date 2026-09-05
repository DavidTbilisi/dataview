from dataclasses import dataclass

from dv.core.datasource import DataSource
from dv.core.query import get_connection
from dv.core.sql import ident

DUCKDB_TYPE_MAP = {
    "INTEGER": "integer",
    "BIGINT": "integer",
    "HUGEINT": "integer",
    "SMALLINT": "integer",
    "TINYINT": "integer",
    "UBIGINT": "integer",
    "UINTEGER": "integer",
    "USMALLINT": "integer",
    "UTINYINT": "integer",
    "FLOAT": "float",
    "DOUBLE": "float",
    "DECIMAL": "float",
    "NUMERIC": "float",
    "REAL": "float",
    "DOUBLE PRECISION": "float",
    "VARCHAR": "text",
    "TEXT": "text",
    "BLOB": "binary",
    "UUID": "text",
    "JSON": "text",
    "ENUM": "text",
    "DATE": "date",
    "TIMESTAMP": "datetime",
    "TIMESTAMP WITH TIME ZONE": "datetime",
    "TIMESTAMPTZ": "datetime",
    "TIMESTAMP_S": "datetime",
    "TIMESTAMP_MS": "datetime",
    "TIMESTAMP_NS": "datetime",
    "TIME": "time",
    "INTERVAL": "interval",
    "BOOLEAN": "boolean",
    "BOOL": "boolean",
}


def _map_type(duck_type: str) -> str:
    base = duck_type.upper().split("(")[0].strip()
    return DUCKDB_TYPE_MAP.get(base, "unknown")


@dataclass
class ColumnInfo:
    name: str
    duck_type: str
    inferred_type: str
    missing: int
    unique: int
    example: str = ""


@dataclass
class SchemaInfo:
    path: str
    format: str
    row_count: int
    columns: list[ColumnInfo]


def get_schema(ds: DataSource) -> SchemaInfo:
    """Describe every column in a single pass over the table."""
    conn = get_connection(ds)
    tbl = ident(ds.table_name)

    col_rows = conn.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = ? ORDER BY ordinal_position",
        [ds.table_name],
    ).fetchall()

    if not col_rows:
        return SchemaInfo(path=str(ds.path), format=ds.format, row_count=0, columns=[])

    # One query computing row count plus missing/unique/example for every column,
    # rather than three separate scans per column.
    parts = ["count(*) AS _rows"]
    for i, (col_name, _) in enumerate(col_rows):
        c = ident(col_name)
        parts.append(f"count(*) FILTER (WHERE {c} IS NULL) AS _missing_{i}")
        parts.append(f"count(DISTINCT {c}) AS _unique_{i}")
        parts.append(f"min({c})::VARCHAR AS _example_{i}")
    agg = conn.execute(f"SELECT {', '.join(parts)} FROM {tbl}").fetchone()

    row_count = agg[0]
    columns = []
    for i, (col_name, duck_type) in enumerate(col_rows):
        missing, unique, example = agg[1 + i * 3], agg[2 + i * 3], agg[3 + i * 3]
        columns.append(
            ColumnInfo(
                name=col_name,
                duck_type=duck_type,
                inferred_type=_map_type(duck_type),
                missing=missing,
                unique=unique,
                example="" if example is None else str(example),
            )
        )

    return SchemaInfo(
        path=str(ds.path),
        format=ds.format,
        row_count=row_count,
        columns=columns,
    )
