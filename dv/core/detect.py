from pathlib import Path

from dv.core.datasource import DataSource
from dv.core.errors import DvError

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

# Formats DuckDB decompresses on the fly, so "data.csv.gz" reads like
# "data.csv". Parquet carries its own compression, and a database file has to
# be opened, not streamed - neither is meaningful gzipped.
GZIPPABLE = {"csv", "tsv", "json", "ndjson"}


def detect_format(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".gz":
        inner = Path(path.stem).suffix.lower()
        fmt = EXTENSION_MAP.get(inner)
        if fmt not in GZIPPABLE:
            raise DvError(
                f"Unsupported gzipped file: {inner or '(none)'}.gz",
                hint=f"Gzip is supported for: {', '.join(sorted(GZIPPABLE))}",
            )
        return fmt
    fmt = EXTENSION_MAP.get(ext)
    if fmt is None:
        raise DvError(
            f"Unsupported file extension: {ext or '(none)'}",
            hint=f"Supported: {', '.join(sorted(EXTENSION_MAP))}",
        )
    return fmt


def make_datasource(
    path: Path,
    table: str | None = None,
    where: str | None = None,
    stream: bool = False,
) -> DataSource:
    fmt = detect_format(path)
    return DataSource(path=path, format=fmt, source_table=table,
                      where=where, stream=stream)
