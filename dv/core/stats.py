from dataclasses import dataclass

from dv.core.datasource import DataSource
from dv.core.query import get_connection
from dv.core.schema import get_schema, SchemaInfo


@dataclass
class NumericStats:
    column: str
    count: int
    min: float
    max: float
    mean: float
    median: float
    std: float


@dataclass
class SummaryStats:
    path: str
    format: str
    row_count: int
    col_count: int
    numeric_cols: list[str]
    text_cols: list[str]
    date_cols: list[str]
    missing_total: int
    duplicate_count: int
    numeric_stats: list[NumericStats]
    date_range: tuple[str, str] | None = None


def get_summary(ds: DataSource) -> SummaryStats:
    schema = get_schema(ds)
    conn = get_connection(ds)
    tbl = ds.table_name

    numeric_cols = [c.name for c in schema.columns if c.inferred_type in ("integer", "float")]
    text_cols = [c.name for c in schema.columns if c.inferred_type == "text"]
    date_cols = [c.name for c in schema.columns if c.inferred_type in ("date", "datetime")]
    missing_total = sum(c.missing for c in schema.columns)

    all_cols = ", ".join(f'"{c.name}"' for c in schema.columns)
    duplicate_count = conn.execute(
        f"SELECT count(*) - count(*) FILTER (WHERE rn = 1) FROM "
        f"(SELECT row_number() OVER (PARTITION BY {all_cols}) as rn FROM {tbl})"
    ).fetchone()[0]

    numeric_stats = []
    for col in numeric_cols:
        safe = f'"{col}"'
        row = conn.execute(
            f"SELECT count({safe}), min({safe}), max({safe}), avg({safe}), "
            f"median({safe}), stddev({safe}) FROM {tbl}"
        ).fetchone()
        numeric_stats.append(NumericStats(
            column=col,
            count=row[0] or 0,
            min=float(row[1]) if row[1] is not None else 0.0,
            max=float(row[2]) if row[2] is not None else 0.0,
            mean=float(row[3]) if row[3] is not None else 0.0,
            median=float(row[4]) if row[4] is not None else 0.0,
            std=float(row[5]) if row[5] is not None else 0.0,
        ))

    date_range = None
    if date_cols:
        safe = f'"{date_cols[0]}"'
        row = conn.execute(
            f"SELECT min({safe}), max({safe}) FROM {tbl} WHERE {safe} IS NOT NULL"
        ).fetchone()
        if row[0] is not None and row[1] is not None:
            date_range = (str(row[0])[:10], str(row[1])[:10])

    return SummaryStats(
        path=str(ds.path),
        format=ds.format,
        row_count=schema.row_count,
        col_count=len(schema.columns),
        numeric_cols=numeric_cols,
        text_cols=text_cols,
        date_cols=date_cols,
        missing_total=missing_total,
        duplicate_count=duplicate_count,
        numeric_stats=numeric_stats,
        date_range=date_range,
    )
