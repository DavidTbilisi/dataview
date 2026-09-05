"""Reading a table from a pipe.

dv scans its input several times - schema, query, aggregates - so stdin is
spooled to a temp file before anything reads it. These tests go through a real
subprocess, because the point is what happens to the actual process's stdin.
"""

import gzip
import json
import subprocess
import sys

import pytest

from dv.core.errors import DvError
from dv.core.stdin import sniff_format

CSV = b"date,category,amount\n2026-06-01,food,10\n2026-06-02,study,20\n"
TSV = b"date\tcategory\tamount\n2026-06-01\tfood\t10\n2026-06-02\tstudy\t20\n"
NDJSON = b'{"category":"food","amount":10}\n{"category":"study","amount":20}\n'
JSON_DOC = b'[{"category":"food","amount":10},{"category":"study","amount":20}]'


def pipe(data: bytes, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "dv.main", *args],
        input=data, capture_output=True, timeout=120,
    )


def ok(data: bytes, *args: str) -> str:
    p = pipe(data, *args)
    assert p.returncode == 0, f"dv {' '.join(args)}\n{p.stderr.decode()}"
    return p.stdout.decode()


# --- sniffing -------------------------------------------------------------

@pytest.mark.parametrize("head,expected", [
    (CSV,                        "csv"),
    (TSV,                        "tsv"),
    (NDJSON,                     "json"),
    (JSON_DOC,                   "json"),
    (b"PAR1\x00\x00",            "parquet"),
    (b"SQLite format 3\x00...",  "sqlite"),
    (b"\n\n\ndate,amount\n1,2",  "csv"),      # leading blank lines
    (b"a;b;c\n1;2;3",            "csv"),      # read_csv_auto sniffs ';' itself
])
def test_sniff(head, expected):
    assert sniff_format(head) == expected


def test_sniff_rejects_an_empty_stream():
    with pytest.raises(DvError, match="Nothing to read"):
        sniff_format(b"   \n\n")


# --- end to end -----------------------------------------------------------

@pytest.mark.parametrize("data", [CSV, TSV, NDJSON, JSON_DOC])
def test_every_text_format_reads_from_a_pipe(data):
    doc = json.loads(ok(data, "--json", "-", "group-by", "category", "--count"))
    assert {r["category"] for r in doc} == {"food", "study"}


def test_gzip_is_decompressed():
    doc = json.loads(ok(gzip.compress(CSV), "--json", "-", "group-by",
                        "category", "--sum", "amount"))
    assert {r["category"] for r in doc} == {"food", "study"}


def test_a_bare_command_reads_the_pipe():
    """`cat f.csv | dv summary` needs no `-`: the first word is a command."""
    doc = json.loads(ok(CSV, "--json", "summary"))
    assert doc["rows"] == 2


def test_a_file_argument_still_wins_over_the_pipe():
    """A pipe left open must not hijack an explicit file."""
    doc = json.loads(ok(CSV, "--json", "examples/expenses.csv", "summary"))
    assert doc["rows"] == 44


def test_global_options_survive_the_rewrite():
    doc = json.loads(ok(CSV, "--json", "-w", "amount > 15", "summary"))
    assert doc["rows"] == 1


def test_the_source_is_named_readably():
    """Reports and titles have to call the pipe something."""
    assert "stdin.csv" in ok(CSV, "-", "summary")


def test_an_empty_pipe_says_so():
    p = pipe(b"", "-", "summary")
    assert p.returncode == 1
    assert b"Nothing to read on stdin" in p.stderr


# --- explicit --format ----------------------------------------------------

def test_format_overrides_a_misleading_name(tmp_path):
    """The escape hatch for a file whose extension does not match its content."""
    f = tmp_path / "access_log"          # no extension at all
    f.write_bytes(CSV)
    doc = json.loads(ok(b"", "--json", "--format", "csv", str(f), "summary"))
    assert doc["rows"] == 2


def test_format_overrides_sniffing_on_a_pipe():
    """A one-column CSV read as TSV: the flag wins, so there is one column."""
    doc = json.loads(ok(CSV, "--json", "--format", "tsv", "-", "summary"))
    assert doc["columns"] == 1


def test_unknown_format_is_rejected():
    p = pipe(b"", "--format", "xml", "examples/expenses.csv", "summary")
    assert p.returncode == 1
    assert b"Unknown format" in p.stderr


def test_format_after_the_file_is_a_position_hint():
    p = pipe(b"", "examples/expenses.csv", "summary", "--format", "csv")
    assert p.returncode == 1
    assert b"has to come before the input file" in p.stderr


# --- the spool is streamed, not buffered ----------------------------------

def test_a_stream_larger_than_the_sniff_buffer_reads_whole():
    """The head is sniffed and written back; the rest is copied through."""
    rows = 50_000
    body = b"".join(f"2026-06-01,c{i % 7},{i}\n".encode() for i in range(rows))
    doc = json.loads(ok(b"date,category,amount\n" + body, "--json", "-", "summary"))
    assert doc["rows"] == rows
