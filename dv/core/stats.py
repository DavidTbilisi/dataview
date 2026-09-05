from dataclasses import dataclass

from dv.core.datasource import DataSource
from dv.core.query import get_connection
from dv.core.schema import get_schema, SchemaInfo
from dv.core.sql import ident
from dv.render.common import fmt_date


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


def get_summary(ds: DataSource, schema: SchemaInfo | None = None) -> SummaryStats:
    """Summarize the source. Pass `schema` to avoid recomputing it."""
    if schema is None:
        schema = get_schema(ds)
    conn = get_connection(ds)
    tbl = ident(ds.table_name)

    numeric_cols = [c.name for c in schema.columns if c.inferred_type in ("integer", "float")]
    text_cols = [c.name for c in schema.columns if c.inferred_type == "text"]
    date_cols = [c.name for c in schema.columns if c.inferred_type in ("date", "datetime")]
    missing_total = sum(c.missing for c in schema.columns)

    duplicate_count = 0
    if schema.columns:
        all_cols = ", ".join(ident(c.name) for c in schema.columns)
        duplicate_count = conn.execute(
            f"SELECT count(*) - count(*) FILTER (WHERE rn = 1) FROM "
            f"(SELECT row_number() OVER (PARTITION BY {all_cols}) as rn FROM {tbl})"
        ).fetchone()[0]

    numeric_stats = []
    if numeric_cols:
        parts = []
        for col in numeric_cols:
            c = ident(col)
            parts += [f"count({c})", f"min({c})", f"max({c})",
                      f"avg({c})", f"median({c})", f"stddev({c})"]
        row = conn.execute(f"SELECT {', '.join(parts)} FROM {tbl}").fetchone()
        for i, col in enumerate(numeric_cols):
            vals = row[i * 6: i * 6 + 6]
            numeric_stats.append(NumericStats(
                column=col,
                count=vals[0] or 0,
                min=float(vals[1]) if vals[1] is not None else 0.0,
                max=float(vals[2]) if vals[2] is not None else 0.0,
                mean=float(vals[3]) if vals[3] is not None else 0.0,
                median=float(vals[4]) if vals[4] is not None else 0.0,
                std=float(vals[5]) if vals[5] is not None else 0.0,
            ))

    date_range = None
    if date_cols:
        safe = ident(date_cols[0])
        row = conn.execute(
            f"SELECT min({safe}), max({safe}) FROM {tbl} WHERE {safe} IS NOT NULL"
        ).fetchone()
        if row[0] is not None and row[1] is not None:
            date_range = (fmt_date(row[0]), fmt_date(row[1]))

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
