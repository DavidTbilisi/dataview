from dataclasses import dataclass

import duckdb

from dv.core.datasource import DataSource
from dv.core.query import get_connection

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
    "VARCHAR": "text",
    "TEXT": "text",
    "BLOB": "text",
    "DATE": "date",
    "TIMESTAMP": "datetime",
    "TIMESTAMP WITH TIME ZONE": "datetime",
    "TIMESTAMPTZ": "datetime",
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
    conn = get_connection(ds)
    tbl = ds.table_name

    col_rows = conn.execute(
        f"SELECT column_name, data_type FROM information_schema.columns "
        f"WHERE table_name = '{tbl}' ORDER BY ordinal_position"
    ).fetchall()

    row_count = conn.execute(f"SELECT count(*) FROM {tbl}").fetchone()[0]

    columns = []
    for col_name, duck_type in col_rows:
        safe = f'"{col_name}"'
        missing = conn.execute(f"SELECT count(*) FROM {tbl} WHERE {safe} IS NULL").fetchone()[0]
        unique = conn.execute(f"SELECT count(DISTINCT {safe}) FROM {tbl}").fetchone()[0]
        ex_row = conn.execute(f"SELECT {safe} FROM {tbl} WHERE {safe} IS NOT NULL LIMIT 1").fetchone()
        example = str(ex_row[0]) if ex_row else ""
        columns.append(
            ColumnInfo(
                name=col_name,
                duck_type=duck_type,
                inferred_type=_map_type(duck_type),
                missing=missing,
                unique=unique,
                example=example,
            )
        )

    return SchemaInfo(
        path=str(ds.path),
        format=ds.format,
        row_count=row_count,
        columns=columns,
    )
