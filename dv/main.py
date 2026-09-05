"""CLI entry point.

Importing the command modules registers their commands on the shared app.
"""

import os

import duckdb

from dv.app import app
from dv.core.errors import DvError
from dv.render.theme import console

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
        app()
        return
    try:
        app()
    except DvError as e:
        console.print(f"[red]Error:[/red] {e.message}")
        if e.hint:
            console.print(f"[dim]{e.hint}[/dim]")
        raise SystemExit(1)
    except duckdb.Error as e:
        console.print(f"[red]Query error:[/red] {str(e).strip().splitlines()[0]}")
        raise SystemExit(1)
    except BrokenPipeError:
        raise SystemExit(0)
    except KeyboardInterrupt:
        raise SystemExit(130)


if __name__ == "__main__":
    cli()
