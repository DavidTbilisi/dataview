"""CLI entry point.

Importing the command modules registers their commands on the shared app.
"""

import os
import sys

import duckdb

from dv.app import app
from dv.core.errors import DvError
from dv.core.stdin import STDIN_ARG
from dv.render.json_out import flush as flush_json
from dv.render.theme import err_console

from dv.commands import (  # noqa: F401  (imported for command registration)
    aggregate,
    charts,
    exports,
    inspect,
    money,
    timeseries,
)


def cli() -> None:
    """Console-script entry point.

    Turns expected failures into a single readable line. Set DV_TRACEBACK=1 to
    see the underlying exception instead.
    """
    if os.environ.get("DV_TRACEBACK"):
        _run()
        return
    try:
        _run()
    except DvError as e:
        err_console.print(f"[red]Error:[/red] {e.message}")
        if e.hint:
            err_console.print(f"[dim]{e.hint}[/dim]")
        raise SystemExit(1)
    except duckdb.Error as e:
        err_console.print(f"[red]Query error:[/red] {str(e).strip().splitlines()[0]}")
        raise SystemExit(1)
    except BrokenPipeError:
        raise SystemExit(0)
    except KeyboardInterrupt:
        raise SystemExit(130)


# Options the Typer callback owns. They must precede the input file, and none
# of them is also a per-command option, so seeing one later is always the
# position mistake rather than a real flag. `--where` is deliberately absent:
# `table` and `streak` take one of their own, and the two compose.
_GLOBAL_ONLY = {"--json", "--unicode", "--ascii", "--table", "--format"}

# Global options whose value is the next argument, needed to tell an option's
# value apart from the input file when scanning argv.
_GLOBAL_VALUE_OPTS = {"--table", "--where", "-w", "--format", "-f"}


def _command_names() -> set[str]:
    return {c.name or c.callback.__name__ for c in app.registered_commands}


def _default_to_stdin() -> None:
    """`cat f.csv | dv summary` means the same as `cat f.csv | dv - summary`.

    Only when the first positional argument is itself a command name, so a real
    file called `summary` would still win - and only when stdin is a pipe, so
    a plain `dv summary` at a prompt keeps its "no input file" advice.
    """
    if sys.stdin.isatty():
        return
    names = _command_names()
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in _GLOBAL_VALUE_OPTS:
            i += 2                      # option and its separate value
        elif arg.startswith("-") and arg != STDIN_ARG:
            i += 1                      # a flag, or --opt=value
        else:
            if arg in names:
                sys.argv.insert(i + 1, STDIN_ARG)
            return


def _check_global_flag_position() -> None:
    """Turn `dv f.csv summary --json` into advice instead of "No such option"."""
    names = _command_names()
    command_at = next((i for i, a in enumerate(sys.argv[1:], 1) if a in names), None)
    if command_at is None:
        return
    for arg in sys.argv[command_at:]:
        if arg in _GLOBAL_ONLY:
            raise DvError(
                f"{arg} has to come before the input file",
                hint=f"Try: dv {arg} <file> {sys.argv[command_at]}",
            )


def _run() -> None:
    """Run the CLI, then write any JSON document the command produced.

    Typer exits by raising SystemExit even on success, so the document is
    written from the handler rather than after the call.
    """
    _default_to_stdin()
    _check_global_flag_position()
    try:
        app()
    except SystemExit as e:
        if e.code in (0, None):
            flush_json(_command_name())
        raise


def _command_name() -> str | None:
    """The subcommand the user typed, for the "no --json here" message."""
    known = _command_names()
    return next((a for a in sys.argv[1:] if a in known), None)


if __name__ == "__main__":
    cli()
