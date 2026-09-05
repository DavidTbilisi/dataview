import glob
import os

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

FORMATS = sorted(set(EXTENSION_MAP.values()))


def check_format(name: str) -> str:
    """Validate a format named by --format, which bypasses extension detection."""
    if name not in FORMATS:
        raise DvError(
            f"Unknown format {name!r}",
            hint=f"Supported: {', '.join(FORMATS)}",
        )
    return name


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


# A path containing any of these is a pattern to expand, not a name to open.
_GLOB_CHARS = "*?["

# Reading several files as one table means concatenating rows, which an
# attached database does not do.
_SINGLE_FILE_ONLY = {"sqlite", "duckdb"}


def is_glob(path: Path) -> bool:
    return any(c in str(path) for c in _GLOB_CHARS)


def expand_glob(pattern: Path) -> list[Path]:
    """Files matching a shell-style pattern, sorted.

    Sorted so that `logs/2026-*.csv` reads in date order, and so two runs over
    the same directory produce the same output.
    """
    matches = sorted(Path(m) for m in glob.glob(str(pattern), recursive=True))
    files = [m for m in matches if m.is_file()]
    if not files:
        raise DvError(
            f"No files match {str(pattern)!r}",
            hint="Quote the pattern so dv expands it: dv 'logs/*.csv' summary",
        )
    return files


def common_format(files: list[Path]) -> str:
    """The one format shared by every file, or an error naming the odd ones out.

    Mixing formats in a single read fails deep inside DuckDB with a message
    about the wrong thing, so it is worth catching here.
    """
    seen: dict[str, list[Path]] = {}
    for f in files:
        seen.setdefault(detect_format(f), []).append(f)
    if len(seen) > 1:
        listed = "; ".join(
            f"{fmt}: {', '.join(p.name for p in group[:3])}"
            f"{'...' if len(group) > 3 else ''}"
            for fmt, group in sorted(seen.items())
        )
        raise DvError(
            f"Mixed formats across {len(files)} files",
            hint=f"Narrow the pattern. Found {listed}",
        )
    return next(iter(seen))


def make_datasource(
    path: Path,
    table: str | None = None,
    where: str | None = None,
    stream: bool = False,
    format: str | None = None,
    files: list[Path] | None = None,
) -> DataSource:
    if files is None:
        files = expand_glob(path) if is_glob(path) else [path]
    elif len(files) > 1 and not is_glob(path):
        # The shell expanded the glob, so `path` is just the first match and
        # naming a report after it would be a lie. Their shared directory is
        # the honest label for the set.
        path = Path(os.path.commonpath([str(f) for f in files]))
    fmt = check_format(format) if format else common_format(files)
    if len(files) > 1 and fmt in _SINGLE_FILE_ONLY:
        raise DvError(
            f"Cannot read {len(files)} {fmt} files as one table",
            hint="Databases hold their own tables; name a single file.",
        )
    return DataSource(path=path, format=fmt, source_table=table,
                      where=where, stream=stream, files=files)
