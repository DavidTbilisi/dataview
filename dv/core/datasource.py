from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DataSource:
    path: Path
    format: str
    table_name: str = "data"
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
