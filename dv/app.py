"""Shared Typer application, console, and input-file context.

Command modules import `app` from here and register on it, so `dv` keeps a
flat `dv <file> <command>` surface rather than nested command groups.
"""

from pathlib import Path
from typing import Optional, Annotated

import typer

from dv.core.config import Config, load_config
from dv.core.datasource import DataSource
from dv.core.detect import make_datasource
from dv.core.errors import DvError
from dv.core.query import require_columns, require_numeric
from dv.core.sql import ident
from dv.render.theme import console, set_charset, set_date_format

app = typer.Typer(
    name="dv",
    help="Personal terminal dataview tool. Usage: dv <file> <command>",
    add_completion=False,
    no_args_is_help=True,
)

_file: Path | None = None
_config: Config = Config()
_source: DataSource | None = None


def config() -> Config:
    """Configuration loaded from .dv.yml, or defaults."""
    return _config


def ds() -> DataSource:
    """The input DataSource, created once per run."""
    global _source
    if _source is not None:
        return _source
    if _file is None:
        raise DvError("No input file given", hint="Usage: dv <file> <command>")
    if not _file.exists():
        raise DvError(f"File not found: {_file}")
    _source = make_datasource(_file)
    return _source


def cols(source: DataSource, *names: str | None) -> tuple[str, ...]:
    """Validate column names against the file, then return them quoted for SQL."""
    require_columns(source, *names)
    return tuple(ident(n) for n in names if n is not None)


def numeric_cols(source: DataSource, *names: str | None) -> tuple[str, ...]:
    """Like `cols`, but also rejects non-numeric columns."""
    require_numeric(source, *names)
    return tuple(ident(n) for n in names if n is not None)


def limit_or_default(limit: int | None, fallback: int = 50) -> int:
    """Resolve a --limit: the flag wins, then .dv.yml, then the command's own default."""
    if limit is not None:
        return limit
    if _config.default_limit is not None:
        return _config.default_limit
    return fallback


def chart_width(width: int | None) -> int | None:
    """Resolve a --width against the configured charts.width."""
    return width if width is not None else _config.charts.width


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    file: Annotated[Optional[Path], typer.Argument(help="Input data file")] = None,
    unicode_: Annotated[Optional[bool], typer.Option(
        "--unicode/--ascii",
        help="Draw charts with Unicode block glyphs instead of plain ASCII.",
    )] = None,
):
    """dv <file> <command> [options]"""
    global _file, _config
    _config = load_config(file.parent if file is not None else None)
    if unicode_ is not None:
        _config.unicode = unicode_
    set_charset(_config.unicode)
    set_date_format(_config.date_format)

    if file is not None:
        _file = file
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        if file is not None:
            name = str(file)
            if name in ctx.command.commands:
                raise DvError(f"No input file given for {name!r}",
                              hint=f"Usage: dv <file> {name}")
            raise DvError(f"No command given for {file}",
                          hint="Try: dv <file> summary")
