"""Aggregates that back the charts.

These check the SQL path agrees with the obvious Python answer, and - the point
of moving them into SQL - that what comes back is bounded by the chart size
rather than by the number of rows.
"""

from pathlib import Path

import duckdb
import pytest

from dv.core.detect import make_datasource
from dv.core.query import run_query
from dv.core.stats import (
    EXACT_POINTS,
    bins_from_values,
    box_stats,
    cross_counts,
    daily_totals,
    numeric_bins,
    scatter_grid,
    spark_series,
)


@pytest.fixture
def expenses():
    return make_datasource(Path("examples/expenses.csv"))


@pytest.fixture
def wide(tmp_path):
    """50k rows - far more than any chart can draw."""
    path = tmp_path / "wide.csv"
    duckdb.sql(
        "COPY (SELECT (i % 97) * 1.5 AS amount, 'cat' || (i % 7) AS category, "
        "DATE '2024-01-01' + INTERVAL (i % 90) DAY AS date FROM range(50000) t(i)) "
        f"TO '{path}' (HEADER)"
    )
    return make_datasource(path)


# --- histogram ---------------------------------------------------------------


def test_numeric_bins_match_python(expenses):
    """The SQL binning agrees with binning the same column in memory."""
    values = [
        float(r["amount"])
        for r in run_query(expenses, "SELECT amount FROM data WHERE amount IS NOT NULL").rows
    ]
    assert [b.count for b in numeric_bins(expenses, "amount", 7)] == \
           [b.count for b in bins_from_values(values, 7)]


def test_numeric_bins_cover_every_row(expenses):
    bins = numeric_bins(expenses, "amount", 9)
    assert sum(b.count for b in bins) == 44        # every non-null row lands in a bucket
    assert len(bins) == 9


def test_numeric_bins_keeps_max_in_last_bucket(wide):
    bins = numeric_bins(wide, "amount", 10)
    assert bins[-1].count > 0


def test_numeric_bins_empty_column(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("amount\n")
    assert numeric_bins(make_datasource(path), "amount", 5) == []


def test_numeric_bins_constant_column(tmp_path):
    path = tmp_path / "const.csv"
    path.write_text("amount\n5\n5\n5\n")
    bins = numeric_bins(make_datasource(path), "amount", 5)
    assert len(bins) == 1 and bins[0].lo == bins[0].hi == 5.0


# --- box ---------------------------------------------------------------------


def test_box_stats_ordering(expenses):
    b = box_stats(expenses, "amount")
    assert b.min <= b.q1 <= b.median <= b.q3 <= b.max
    assert b.count == 44


def test_box_stats_needs_four_values(tmp_path):
    path = tmp_path / "tiny.csv"
    path.write_text("amount\n1\n2\n")
    assert box_stats(make_datasource(path), "amount") is None


# --- scatter -----------------------------------------------------------------


def test_scatter_exact_below_threshold():
    """Small inputs keep every point, so the plot is not shifted by binning."""
    ds = make_datasource(Path("examples/study.csv"))
    grid = scatter_grid(ds, "study_hours", "score")
    assert all(w == 1 for _, _, w in grid.points)


def test_scatter_bins_large_inputs(wide):
    grid = scatter_grid(wide, "amount", "amount")
    assert len(grid.points) < EXACT_POINTS
    assert sum(w for _, _, w in grid.points) == 50000   # no row is dropped


def test_scatter_bounds_are_the_real_range(wide):
    grid = scatter_grid(wide, "amount", "amount")
    assert grid.x_min == 0.0
    assert grid.x_max == 96 * 1.5


def test_scatter_empty(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("a,b\n")
    assert scatter_grid(make_datasource(path), "a", "b") is None


# --- sparkline ---------------------------------------------------------------


def test_spark_series_is_capped(wide):
    """50k rows must not become 50k glyphs."""
    assert len(spark_series(wide, "amount", points=60)) == 60


def test_spark_series_keeps_small_series_intact(expenses):
    assert len(spark_series(expenses, "amount", order_by="date", points=80)) == 44


def test_spark_series_follows_the_order_column(tmp_path):
    path = tmp_path / "ordered.csv"
    path.write_text("v,t\n3,3\n1,1\n2,2\n")
    assert spark_series(make_datasource(path), "v", order_by="t", points=80) == [1.0, 2.0, 3.0]


# --- heatmap and calendar ----------------------------------------------------


def test_cross_counts_total(expenses):
    assert sum(n for _, _, n in cross_counts(expenses, "category", "method")) == 44


def test_cross_counts_is_bounded_by_cardinality(wide):
    """One row per category pair, not per input row."""
    assert len(cross_counts(wide, "category", "category")) == 7


def test_daily_totals_one_row_per_day(wide):
    totals = daily_totals(wide, "date", "amount")
    assert len(totals) == 90
    assert totals == sorted(totals)


def test_daily_totals_counts_without_a_value_column(expenses):
    assert sum(v for _, v in daily_totals(expenses, "date")) == 44
