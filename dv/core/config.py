"""Optional `.dv.yml` configuration.

Looked up next to the input file, then in the working directory, then in the
home directory. The first file found wins.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from dv.core.errors import DvError

CONFIG_NAME = ".dv.yml"


@dataclass
class ChartConfig:
    width: int | None = None


@dataclass
class Config:
    default_limit: int | None = None   # None = each command keeps its own default
    unicode: bool = False
    date_format: str = "%Y-%m-%d"
    charts: ChartConfig = field(default_factory=ChartConfig)
    aliases: dict = field(default_factory=dict)
    budget: dict = field(default_factory=dict)
    path: Path | None = None


def _parse(path: Path) -> Config:
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise DvError(f"Could not parse {path}", hint=str(e).splitlines()[0]) from e
    if not isinstance(data, dict):
        raise DvError(f"{path} must contain a mapping at the top level")

    cfg = Config(path=path)
    if "default_limit" in data:
        cfg.default_limit = int(data["default_limit"])
    if "unicode" in data:
        cfg.unicode = bool(data["unicode"])
    if "date_format" in data:
        cfg.date_format = str(data["date_format"])
    if "charts" in data:
        charts = data["charts"] or {}
        width = charts.get("width")
        cfg.charts = ChartConfig(width=int(width) if width is not None else None)
    if "aliases" in data:
        cfg.aliases = data["aliases"] or {}
    if "budget" in data:
        cfg.budget = data["budget"] or {}
    return cfg


def load_config(search_dir: Path | None = None) -> Config:
    """Load the nearest .dv.yml, or return defaults if there is none.

    Always returns a fresh Config: callers mutate it (the --unicode flag
    overrides the file), so a shared instance would leak between loads.
    """
    candidates = []
    if search_dir:
        candidates.append(search_dir / CONFIG_NAME)
    candidates.append(Path.cwd() / CONFIG_NAME)
    candidates.append(Path.home() / CONFIG_NAME)

    for path in candidates:
        if path.exists():
            return _parse(path)
    return Config()
