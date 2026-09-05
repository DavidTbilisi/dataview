"""Machine-readable output.

`--json` turns every supported command into something a script can consume.
Renderers call `emit()` with the data they were about to draw, rather than a
transcription of the drawing, so `dv f.csv group-by category --sum amount --json`
gives the rows themselves and pipes straight into jq.

The terminal console is silenced while this is on, so ASCII can never leak into
a pipe. A command with no `emit()` call has no JSON form yet, and `flush()`
says so instead of printing nothing.
"""

import json
import sys
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from dv.core.errors import DvError
from dv.render import theme

_enabled = False
_sections: list[tuple[str, object]] = []


def set_json(on: bool) -> None:
    """Turn JSON output on, silencing the terminal renderers."""
    global _enabled, _sections
    _enabled = on
    _sections = []
    theme.console.quiet = on


def json_mode() -> bool:
    return _enabled


def emit(name: str, payload) -> None:
    """Record one section of output. Ignored unless --json is on."""
    if _enabled:
        _sections.append((name, payload))


def _default(o):
    """Render the types DuckDB hands back that JSON has no opinion about."""
    if isinstance(o, (datetime, date, time)):
        return o.isoformat()
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, timedelta):
        return o.total_seconds()
    if isinstance(o, (bytes, bytearray, memoryview)):
        return bytes(o).decode("utf-8", "replace")
    if is_dataclass(o) and not isinstance(o, type):
        return asdict(o)
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    return str(o)


def flush(command: str | None = None) -> None:
    """Write the document. One section prints bare; several print keyed by name."""
    if not _enabled:
        return
    if not _sections:
        raise DvError(
            f"--json is not supported by {command!r}" if command
            else "--json is not supported by this command",
            hint="Every command that renders data supports it; the exporters "
                 "write a file instead, so use their own output path.",
        )
    payload = _sections[0][1] if len(_sections) == 1 else dict(_sections)
    json.dump(payload, sys.stdout, default=_default, indent=2)
    sys.stdout.write("\n")
