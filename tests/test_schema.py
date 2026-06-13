from pathlib import Path
import pytest

from dv.core.detect import make_datasource
from dv.core.schema import get_schema


@pytest.fixture
def expenses_ds(tmp_path):
    f = tmp_path / "expenses.csv"
    f.write_text(
        "date,category,amount,method\n"
        "2026-06-01,food,25.50,cash\n"
        "2026-06-02,study,12.00,card\n"
        "2026-06-03,food,,cash\n"
    )
    return make_datasource(f)


def test_row_count(expenses_ds):
    schema = get_schema(expenses_ds)
    assert schema.row_count == 3


def test_column_names(expenses_ds):
    schema = get_schema(expenses_ds)
    names = [c.name for c in schema.columns]
    assert "category" in names
    assert "amount" in names


def test_missing_count(expenses_ds):
    schema = get_schema(expenses_ds)
    amount_col = next(c for c in schema.columns if c.name == "amount")
    assert amount_col.missing == 1


def test_type_inference(expenses_ds):
    schema = get_schema(expenses_ds)
    by_name = {c.name: c for c in schema.columns}
    assert by_name["amount"].inferred_type == "float"
    assert by_name["category"].inferred_type == "text"
