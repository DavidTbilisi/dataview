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
    # Cached DuckDB connection, populated on first query. Not part of equality
    # or the constructor signature.
    connection: Any = field(default=None, init=False, repr=False, compare=False)

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None


@dataclass
class ResultView:
    columns: list[str]
    rows: list[dict]
    metadata: dict = field(default_factory=dict)
