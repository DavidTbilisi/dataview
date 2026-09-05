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


# --- Chart aggregates ---------------------------------------------------------
#
# Every function below returns at most a screenful of numbers. Charts used to
# pull whole columns into Python to bin them there, which cost gigabytes on a
# large file to draw a few dozen glyphs; DuckDB does the same arithmetic over
# the materialized table and hands back only the buckets.


@dataclass
class Bin:
    lo: float
    hi: float
    count: int


def numeric_bins(ds: DataSource, column: str, bins: int = 10) -> list[Bin]:
    """Equal-width histogram buckets for a numeric column.

    Returns [] when the column is empty, and a single bin with lo == hi when
    every value is identical - both cases the renderer reports rather than draws.
    """
    conn = get_connection(ds)
    tbl, col = ident(ds.table_name), ident(column)

    row = conn.execute(
        f"SELECT min({col}), max({col}), count({col}) FROM {tbl}"
    ).fetchone()
    mn, mx, count = row
    if not count or mn is None:
        return []
    mn, mx = float(mn), float(mx)
    if mn == mx:
        return [Bin(lo=mn, hi=mn, count=count)]

    bins = max(1, bins)
    step = (mx - mn) / bins
    # least(...) keeps the maximum value in the last bucket instead of a
    # bucket of its own just past the end.
    counts = dict(
        conn.execute(
            f"SELECT least(floor(({col} - {mn}) / {step}), {bins - 1})::INTEGER AS idx, "
            f"count(*) FROM {tbl} WHERE {col} IS NOT NULL GROUP BY idx"
        ).fetchall()
    )
    return [
        Bin(lo=mn + i * step, hi=mn + (i + 1) * step, count=counts.get(i, 0))
        for i in range(bins)
    ]


def bins_from_values(values: list[float], bins: int = 10) -> list[Bin]:
    """Same buckets as `numeric_bins`, for callers that already hold the values.

    Only for series that are small by construction - one point per row of a
    already-aggregated result. Anything reading a whole column belongs in SQL.
    """
    if not values:
        return []
    mn, mx = float(min(values)), float(max(values))
    if mn == mx:
        return [Bin(lo=mn, hi=mn, count=len(values))]

    bins = max(1, bins)
    step = (mx - mn) / bins
    counts = [0] * bins
    for v in values:
        counts[min(int((v - mn) / step), bins - 1)] += 1
    return [
        Bin(lo=mn + i * step, hi=mn + (i + 1) * step, count=c)
        for i, c in enumerate(counts)
    ]


@dataclass
class BoxStats:
    count: int
    min: float
    q1: float
    median: float
    q3: float
    max: float


def box_stats(ds: DataSource, column: str) -> BoxStats | None:
    """Five-number summary for a numeric column. None when there is too little data."""
    conn = get_connection(ds)
    tbl, col = ident(ds.table_name), ident(column)
    row = conn.execute(
        f"SELECT count({col}), min({col}), quantile_cont({col}, 0.25), "
        f"median({col}), quantile_cont({col}, 0.75), max({col}) FROM {tbl}"
    ).fetchone()
    if not row[0] or row[0] < 4:
        return None
    return BoxStats(
        count=row[0],
        min=float(row[1]), q1=float(row[2]), median=float(row[3]),
        q3=float(row[4]), max=float(row[5]),
    )


# Scatter points are binned in SQL at a resolution finer than any terminal, so
# the renderer can fold them onto its own grid without a visible shift. Below
# EXACT_POINTS the raw points are cheap to carry, and plotting them places every
# dot exactly where it belongs rather than within a cell of it.
SCATTER_RESOLUTION = (400, 100)
EXACT_POINTS = 20_000


@dataclass
class ScatterGrid:
    points: list[tuple[float, float, int]]   # x, y, weight
    x_min: float
    x_max: float
    y_min: float
    y_max: float


def scatter_grid(ds: DataSource, x_col: str, y_col: str) -> ScatterGrid | None:
    """Aggregate two numeric columns onto a fixed grid of at most 400x100 cells."""
    conn = get_connection(ds)
    tbl, x, y = ident(ds.table_name), ident(x_col), ident(y_col)
    where = f"WHERE {x} IS NOT NULL AND {y} IS NOT NULL"

    bounds = conn.execute(
        f"SELECT min({x}), max({x}), min({y}), max({y}), count(*) FROM {tbl} {where}"
    ).fetchone()
    if not bounds[4]:
        return None
    x_min, x_max, y_min, y_max = (float(v) for v in bounds[:4])

    if bounds[4] <= EXACT_POINTS:
        rows = conn.execute(f"SELECT {x}, {y} FROM {tbl} {where}").fetchall()
        return ScatterGrid(
            points=[(float(a), float(b), 1) for a, b in rows],
            x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max,
        )

    gw, gh = SCATTER_RESOLUTION
    x_rng = (x_max - x_min) or 1.0
    y_rng = (y_max - y_min) or 1.0
    rows = conn.execute(
        f"SELECT least(floor(({x} - {x_min}) / {x_rng} * {gw - 1}), {gw - 1}) AS gx, "
        f"       least(floor(({y} - {y_min}) / {y_rng} * {gh - 1}), {gh - 1}) AS gy, "
        f"       count(*) FROM {tbl} {where} GROUP BY gx, gy"
    ).fetchall()

    return ScatterGrid(
        points=[
            (x_min + gx / (gw - 1) * x_rng, y_min + gy / (gh - 1) * y_rng, n)
            for gx, gy, n in rows
        ],
        x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max,
    )


def spark_series(
    ds: DataSource,
    column: str,
    order_by: str | None = None,
    points: int = 80,
) -> list[float]:
    """At most `points` averaged samples of a column, in order.

    A sparkline draws one glyph per value, so a column of a million rows used to
    become a million-character line. NTILE averages within each glyph instead.
    """
    conn = get_connection(ds)
    tbl, col = ident(ds.table_name), ident(column)
    order = f"ORDER BY {ident(order_by)}" if order_by else ""
    rows = conn.execute(
        f"SELECT avg({col}) FROM ("
        f"  SELECT {col}, ntile({max(1, points)}) OVER ({order}) AS _tile"
        f"  FROM {tbl} WHERE {col} IS NOT NULL"
        f") GROUP BY _tile ORDER BY _tile"
    ).fetchall()
    return [float(r[0]) for r in rows if r[0] is not None]


def cross_counts(ds: DataSource, row_col: str, col_col: str) -> list[tuple[str, str, int]]:
    """Row/column/count triples for a heatmap, counted in SQL."""
    conn = get_connection(ds)
    tbl = ident(ds.table_name)
    r, c = ident(row_col), ident(col_col)
    return [
        (str(a), str(b), n)
        for a, b, n in conn.execute(
            f"SELECT {r}, {c}, count(*) FROM {tbl} "
            f"WHERE {r} IS NOT NULL AND {c} IS NOT NULL GROUP BY {r}, {c}"
        ).fetchall()
    ]


def daily_totals(
    ds: DataSource,
    date_col: str,
    value_col: str | None = None,
) -> list[tuple[str, float]]:
    """One (date, value) pair per day, summed in SQL, for the calendar heatmap."""
    conn = get_connection(ds)
    tbl, d = ident(ds.table_name), ident(date_col)
    value = f"sum({ident(value_col)})" if value_col else "count(*)"
    return [
        (str(day), float(total or 0))
        for day, total in conn.execute(
            f"SELECT {d}::DATE AS _day, {value} FROM {tbl} "
            f"WHERE {d} IS NOT NULL GROUP BY _day ORDER BY _day"
        ).fetchall()
    ]
