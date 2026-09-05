"""Reading many files as one table.

A quoted pattern (`dv 'logs/*.csv' summary`) is expanded by dv; an unquoted one
is expanded by the shell into several arguments before dv sees it. Both have to
end up at the same table, so the quoted form is tested through the CLI runner
and the expanded form through a real subprocess, where argv is what a shell
would have produced.
"""

import gzip
import json
import sqlite3
import subprocess
import sys

from pathlib import Path

import pytest
from typer.testing import CliRunner

import dv.main  # noqa: F401  (registers all commands)
from dv.app import app
from dv.core.detect import common_format, expand_glob, is_glob
from dv.core.errors import DvError

from tests.test_cli import run
from tests.test_json import run_json as as_json   # --json is flushed at exit

runner = CliRunner()

JAN = "date,level,ms\n2026-01-01,info,10\n2026-01-02,error,20\n"
FEB = "date,level,ms\n2026-02-01,info,30\n2026-02-02,warn,40\n"
# A column the other two do not have, to prove nothing is silently dropped.
MAR = "date,level,ms,note\n2026-03-01,info,50,late\n"


@pytest.fixture
def logs(tmp_path):
    d = tmp_path / "logs"
    d.mkdir()
    for name, body in (("jan.csv", JAN), ("feb.csv", FEB), ("mar.csv", MAR)):
        (d / name).write_text(body)
    return d


def shell(*args: str) -> subprocess.CompletedProcess:
    """Run the real entry point, the way a shell would after expanding a glob."""
    return subprocess.run([sys.executable, "-m", "dv.main", *args],
                          capture_output=True, text=True, timeout=120)


# --- expansion ------------------------------------------------------------

def test_is_glob():
    assert not is_glob(Path("a.csv"))
    assert is_glob(Path("logs/*.csv"))


def test_expand_is_sorted(logs):
    assert [p.name for p in expand_glob(logs / "*.csv")] == \
        ["feb.csv", "jan.csv", "mar.csv"]


def test_expand_with_no_matches(logs):
    with pytest.raises(DvError, match="No files match"):
        expand_glob(logs / "*.parquet")


def test_directories_are_not_input(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.csv").write_text(JAN)
    assert [p.name for p in expand_glob(tmp_path / "*")] == ["a.csv"]


def test_mixed_formats_are_refused(logs):
    (logs / "x.parquet").write_bytes(b"PAR1")
    with pytest.raises(DvError, match="Mixed formats"):
        common_format(expand_glob(logs / "*"))


def test_gzip_counts_as_its_inner_format(logs):
    (logs / "apr.csv.gz").write_bytes(gzip.compress(JAN.encode()))
    assert common_format(expand_glob(logs / "*")) == "csv"


# --- reading --------------------------------------------------------------

def test_a_quoted_glob_reads_every_file(logs):
    assert as_json([str(logs / "*.csv"), "summary"])["rows"] == 5


def test_the_shell_expanded_form_reads_every_file(logs):
    p = shell("--json", *sorted(str(f) for f in logs.glob("*.csv")), "summary")
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)["rows"] == 5


def test_summary_states_the_file_count(logs):
    assert as_json([str(logs / "*.csv"), "summary"])["files"] == 3


def test_rows_are_tagged_with_their_file(logs):
    rows = as_json([str(logs / "*.csv"), "group-by", "filename", "--count"])
    assert {r["filename"]: r["count"] for r in rows} == \
        {"jan.csv": 2, "feb.csv": 2, "mar.csv": 1}


def test_a_column_in_only_one_file_survives(logs):
    """Without union_by_name DuckDB drops it from every file, silently."""
    cols = {c["name"] for c in as_json([str(logs / "*.csv"), "schema"])["columns"]}
    assert "note" in cols


def test_a_single_match_is_an_ordinary_file(logs):
    """One file is not a set: no filename column appears out of nowhere."""
    cols = {c["name"] for c in as_json([str(logs / "jan*.csv"), "schema"])["columns"]}
    assert cols == {"date", "level", "ms"}


def test_where_applies_across_the_set(logs):
    rows = as_json(["--where", "level = 'info'", str(logs / "*.csv"),
                    "group-by", "filename", "--count"])
    assert sum(r["count"] for r in rows) == 3


def test_an_existing_filename_column_is_not_clobbered(tmp_path):
    d = tmp_path / "c"
    d.mkdir()
    (d / "one.csv").write_text("filename,n\na,1\n")
    (d / "two.csv").write_text("filename,n\nb,2\n")
    rows = as_json([str(d / "*.csv"), "table"])
    assert {r["filename"] for r in rows} == {"a", "b"}      # the data's own
    assert {r["_filename"] for r in rows} == {"one.csv", "two.csv"}


def test_databases_cannot_be_concatenated(tmp_path):
    for name in ("a.db", "b.db"):
        conn = sqlite3.connect(tmp_path / name)
        conn.execute("CREATE TABLE t(id INTEGER)")
        conn.commit()
        conn.close()
    with pytest.raises(DvError, match="Cannot read 2 sqlite files"):
        runner.invoke(app, [str(tmp_path / "*.db"), "summary"],
                      catch_exceptions=False)


def test_parquet_globs(tmp_path, logs):
    run([str(logs / "jan.csv"), "query",
         f"COPY (SELECT * FROM data) TO '{tmp_path / 'a.parquet'}'"])
    run([str(logs / "feb.csv"), "query",
         f"COPY (SELECT * FROM data) TO '{tmp_path / 'b.parquet'}'"])
    assert as_json([str(tmp_path / "*.parquet"), "summary"])["rows"] == 4


# --- argv handling --------------------------------------------------------

def test_a_bad_command_is_not_mistaken_for_a_file(logs):
    """`dv f.csv nosuchthing` is a missing command, not a missing file."""
    p = shell(str(logs / "jan.csv"), "nosuchthing")
    assert p.returncode != 0
    assert "No such command" in p.stderr or "No such command" in p.stdout


def test_a_missing_file_among_real_ones_is_reported(logs):
    p = shell(str(logs / "jan.csv"), str(logs / "feb.csv"), str(logs / "gone.csv"),
              "summary")
    assert p.returncode == 1
    assert "File not found" in p.stderr


def test_global_options_are_not_mistaken_for_files(logs):
    p = shell("--json", "-w", "ms > 15", *sorted(str(f) for f in logs.glob("*.csv")),
              "summary")
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)["rows"] == 4
