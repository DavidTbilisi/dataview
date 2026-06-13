from pathlib import Path
import pytest

from dv.core.detect import make_datasource
from dv.core.query import run_query, run_table_query


@pytest.fixture
def ds(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text("name,value\nalice,10\nbob,20\ncarol,30\n")
    return make_datasource(f)


def test_run_query_columns(ds):
    result = run_query(ds, "SELECT name FROM data")
    assert result.columns == ["name"]


def test_run_query_rows(ds):
    result = run_query(ds, "SELECT * FROM data ORDER BY value")
    assert len(result.rows) == 3
    assert result.rows[0]["name"] == "alice"


def test_run_table_query_limit(ds):
    result = run_table_query(ds, limit=2)
    assert len(result.rows) == 2


def test_run_table_query_where(ds):
    result = run_table_query(ds, where="value > 15")
    assert all(r["value"] > 15 for r in result.rows)


def test_run_table_query_sort(ds):
    result = run_table_query(ds, sort="value", desc=True)
    values = [r["value"] for r in result.rows]
    assert values == sorted(values, reverse=True)
