from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ChartConfig:
    width: int = 60


@dataclass
class Config:
    default_limit: int = 50
    unicode: bool = False
    date_format: str = "%Y-%m-%d"
    charts: ChartConfig = field(default_factory=ChartConfig)
    aliases: dict = field(default_factory=dict)


_DEFAULT_CONFIG = Config()


def load_config(search_dir: Path | None = None) -> Config:
    candidates = []
    if search_dir:
        candidates.append(search_dir / ".dv.yml")
    candidates.append(Path.cwd() / ".dv.yml")
    candidates.append(Path.home() / ".dv.yml")

    for path in candidates:
        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f) or {}
            cfg = Config()
            if "default_limit" in data:
                cfg.default_limit = int(data["default_limit"])
            if "unicode" in data:
                cfg.unicode = bool(data["unicode"])
            if "date_format" in data:
                cfg.date_format = str(data["date_format"])
            if "charts" in data:
                charts = data["charts"]
                cfg.charts = ChartConfig(width=int(charts.get("width", 60)))
            if "aliases" in data:
                cfg.aliases = data["aliases"]
            return cfg

    return _DEFAULT_CONFIG
