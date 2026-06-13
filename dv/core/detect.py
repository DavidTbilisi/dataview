from pathlib import Path

from dv.core.datasource import DataSource

EXTENSION_MAP = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".json": "json",
    ".jsonl": "ndjson",
    ".ndjson": "ndjson",
    ".parquet": "parquet",
    ".sqlite": "sqlite",
    ".db": "sqlite",
    ".duckdb": "duckdb",
}


def detect_format(path: Path) -> str:
    ext = path.suffix.lower()
    fmt = EXTENSION_MAP.get(ext)
    if fmt is None:
        raise ValueError(f"Unsupported file extension: {ext!r}")
    return fmt


def make_datasource(path: Path) -> DataSource:
    fmt = detect_format(path)
    return DataSource(path=path, format=fmt)
