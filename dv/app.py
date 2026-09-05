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
from dv.core.stdin import is_stdin, spool_stdin
from dv.core.query import require_columns, require_numeric
from dv.core.sql import ident
from dv.render.json_out import set_json
from dv.render.theme import console, set_charset, set_date_format

app = typer.Typer(
    name="dv",
    help="Personal terminal dataview tool. Usage: dv <file> <command>",
    add_completion=False,
    no_args_is_help=True,
)

_file: Path | None = None
_format: str | None = None
_table: str | None = None
_where: str | None = None
_config: Config = Config()
_source: DataSource | None = None


def config() -> Config:
    """Configuration loaded from .dv.yml, or defaults."""
    return _config


def where() -> str | None:
    """The global --where condition, if one was given."""
    return _where


def ds(stream: bool = False) -> DataSource:
    """The input DataSource, created once per run.

    Pass `stream=True` from a command that reads the file once and bounded - a
    peek at the first rows rather than a scan. It registers `data` as a view so
    DuckDB can push the LIMIT into the scan; anything that queries the source
    repeatedly wants the default materialized table instead.
    """
    global _source
    if _source is not None:
        return _source
    if _file is None:
        raise DvError("No input file given", hint="Usage: dv <file> <command>")
    path, fmt = _file, _format
    if is_stdin(path):
        # A pipe is read once, here, and every command downstream sees a file.
        path, fmt = spool_stdin(fmt)
    elif not path.exists():
        raise DvError(f"File not found: {path}")
    _source = make_datasource(path, table=_table, where=_where,
                              stream=stream, format=fmt)
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
    file: Annotated[Optional[Path], typer.Argument(help="Input data file, or - to read stdin")] = None,
    unicode_: Annotated[Optional[bool], typer.Option(
        "--unicode/--ascii",
        help="Draw charts with Unicode block glyphs instead of plain ASCII.",
    )] = None,
    format_: Annotated[Optional[str], typer.Option(
        "--format", "-f",
        help="Read the input as this format instead of guessing from its name.",
    )] = None,
    table: Annotated[Optional[str], typer.Option(
        "--table",
        help="Which table to read from a multi-table SQLite/DuckDB file.",
    )] = None,
    where: Annotated[Optional[str], typer.Option(
        "--where", "-w",
        help="SQL condition every command sees, e.g. --where \"amount > 100\".",
    )] = None,
    json_: Annotated[bool, typer.Option(
        "--json",
        help="Emit the command's data as JSON instead of drawing it.",
    )] = False,
):
    """dv <file> <command> [options]"""
    global _file, _format, _table, _where, _config, _source
    # One process normally runs one command, but tests (and any future
    # interactive mode) invoke the app repeatedly: without this the cached
    # source from the previous run would answer for the new file.
    if _source is not None:
        _source.close()
        _source = None
    _config = load_config(
        file.parent if file is not None and not is_stdin(file) else None
    )
    if unicode_ is not None:
        _config.unicode = unicode_
    set_charset(_config.unicode)
    set_date_format(_config.date_format)
    set_json(json_)

    if file is not None:
        _file = file
    _format = format_
    _table = table
    _where = where
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        if file is not None:
            name = str(file)
            if name in ctx.command.commands:
                raise DvError(f"No input file given for {name!r}",
                              hint=f"Usage: dv <file> {name}")
            raise DvError(
                "No command given for stdin" if is_stdin(file)
                else f"No command given for {file}",
                hint="Try: dv <file> summary",
            )
