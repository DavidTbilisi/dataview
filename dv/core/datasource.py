from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DataSource:
    path: Path
    format: str
    table_name: str = "data"


@dataclass
class ResultView:
    columns: list[str]
    rows: list[dict]
    metadata: dict = field(default_factory=dict)
