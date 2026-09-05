from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DataSource:
    path: Path
    format: str
    table_name: str = "data"
    # For multi-table SQLite/DuckDB files: which table becomes `data`.
    source_table: str | None = None
    # A global --where, applied while `data` is being loaded so that every
    # command sees the filtered rows without knowing about the flag.
    where: str | None = None
    # Every file the input expands to. A glob or several paths on the command
    # line read as one table; `path` stays what the user typed, so messages and
    # report titles can still name the input.
    files: list[Path] = field(default_factory=list)
    # Register `data` as a view rather than a materialized table. Set by the
    # commands that read the file once and bounded, so DuckDB can push their
    # LIMIT into the scan instead of parsing the whole file first.
    stream: bool = False
    # Cached DuckDB connection, populated on first query. Not part of equality
    # or the constructor signature.
    connection: Any = field(default=None, init=False, repr=False, compare=False)

    @property
    def paths(self) -> list[Path]:
        """The files to read - always at least one."""
        return self.files or [self.path]

    @property
    def multi(self) -> bool:
        return len(self.files) > 1

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None


@dataclass
class ResultView:
    columns: list[str]
    rows: list[dict]
    metadata: dict = field(default_factory=dict)
