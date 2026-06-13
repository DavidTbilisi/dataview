from pathlib import Path
import pytest

from dv.core.detect import detect_format, make_datasource


def test_csv():
    assert detect_format(Path("data.csv")) == "csv"


def test_tsv():
    assert detect_format(Path("data.tsv")) == "tsv"


def test_json():
    assert detect_format(Path("data.json")) == "json"


def test_jsonl():
    assert detect_format(Path("data.jsonl")) == "ndjson"


def test_ndjson():
    assert detect_format(Path("data.ndjson")) == "ndjson"


def test_parquet():
    assert detect_format(Path("data.parquet")) == "parquet"


def test_sqlite():
    assert detect_format(Path("data.sqlite")) == "sqlite"
    assert detect_format(Path("data.db")) == "sqlite"


def test_duckdb():
    assert detect_format(Path("data.duckdb")) == "duckdb"


def test_unknown_raises():
    with pytest.raises(ValueError, match="Unsupported"):
        detect_format(Path("data.xyz"))


def test_make_datasource(tmp_path):
    f = tmp_path / "test.csv"
    f.write_text("a,b\n1,2\n")
    ds = make_datasource(f)
    assert ds.format == "csv"
    assert ds.table_name == "data"
