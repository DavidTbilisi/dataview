"""Reading a table from a pipe.

Every reader in dv scans its input more than once - the schema, then the query,
then the aggregates - and a pipe can only be read once. So stdin is spooled to
a temporary file and the rest of the tool sees an ordinary path, with no reader
needing to know where the bytes came from.

The spool is streamed in chunks rather than buffered, so piping a file larger
than memory works.
"""

import atexit
import shutil
import sys
import tempfile
import zlib

from pathlib import Path

from dv.core.detect import check_format
from dv.core.errors import DvError

STDIN_ARG = "-"

# Enough of the stream to see a magic number and a header line.
_SNIFF_BYTES = 64 * 1024

_SUFFIX = {
    "csv": ".csv",
    "tsv": ".tsv",
    "json": ".json",
    "ndjson": ".ndjson",
    "parquet": ".parquet",
    "sqlite": ".sqlite",
    "duckdb": ".duckdb",
}

_GZIP_MAGIC = b"\x1f\x8b"


def is_stdin(path: Path) -> bool:
    return str(path) == STDIN_ARG


def sniff_format(head: bytes) -> str:
    """Guess a format from the first bytes of a stream.

    A pipe has no filename to read an extension off, so the content has to say
    what it is. Binary formats announce themselves with a magic number; text
    formats are told apart by their first non-empty line.
    """
    if head.startswith(b"PAR1"):
        return "parquet"
    if head.startswith(b"SQLite format 3\x00"):
        return "sqlite"
    if head.startswith(b"DUCK") or head[8:12] == b"DUCK":
        return "duckdb"

    first = ""
    for line in head.decode("utf-8", "replace").splitlines():
        if line.strip():
            first = line.strip()
            break
    if not first:
        raise DvError(
            "Nothing to read on stdin",
            hint="Pipe a file in, or name one: dv <file> <command>",
        )

    if first[0] in "{[":
        # read_json_auto detects both a single document and one object per
        # line, so there is nothing to tell apart here.
        return "json"
    # read_csv_auto sniffs ',', ';' and '|' by itself; only a tab needs saying,
    # because tsv passes it as an explicit delimiter.
    return "tsv" if first.count("\t") > first.count(",") else "csv"


def _sniff_gzip(head: bytes) -> str:
    """Format of the data *inside* a gzip stream, from its first block."""
    try:
        inner = zlib.decompressobj(wbits=31).decompress(head, _SNIFF_BYTES)
    except zlib.error as e:
        raise DvError("Could not read the gzip stream on stdin", hint=str(e))
    fmt = sniff_format(inner)
    if fmt in ("parquet", "sqlite", "duckdb"):
        raise DvError(f"A gzipped {fmt} file is not readable as a stream")
    return fmt


def spool_stdin(fmt: str | None = None) -> tuple[Path, str]:
    """Copy stdin to a temp file and return its path and format.

    `fmt` names the format explicitly (from --format); without it the content
    is sniffed. The file is named `stdin.<ext>` inside a temp directory so that
    reports and error messages have something readable to call it.
    """
    stream = sys.stdin.buffer
    head = stream.read(_SNIFF_BYTES)
    gzipped = head.startswith(_GZIP_MAGIC)

    if fmt is None:
        fmt = _sniff_gzip(head) if gzipped else sniff_format(head)
    else:
        check_format(fmt)

    directory = Path(tempfile.mkdtemp(prefix="dv-stdin-"))
    atexit.register(shutil.rmtree, directory, ignore_errors=True)
    suffix = _SUFFIX[fmt] + (".gz" if gzipped else "")
    path = directory / f"stdin{suffix}"

    # Written back-to-front: the sniffed head first, then the rest of the pipe
    # streamed through, so input larger than memory still works.
    with path.open("wb") as f:
        f.write(head)
        shutil.copyfileobj(stream, f)

    return path, fmt
