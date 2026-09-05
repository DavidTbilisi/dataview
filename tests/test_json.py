"""`--json` output.

The contract is: stdout carries one JSON document and nothing else, so a
command can be piped into jq. These tests parse what comes back rather than
matching text, and cover every command through the same case table the ASCII
smoke tests use, so a new command cannot quietly ship without a JSON form.
"""

import io
import json
import subprocess
import sys
from contextlib import redirect_stdout

import pytest
from typer.testing import CliRunner

import dv.main  # noqa: F401  (registers all commands)
from dv.app import app
from dv.core.errors import DvError
from dv.render import theme
from dv.render.json_out import flush, set_json

from tests.test_cli import CASES, EXPENSES, MONEY, TASKS

runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_json_mode():
    """--json silences the shared console; leave it as it was found."""
    yield
    set_json(False)
    theme.console.quiet = False


def run_json(argv: list[str]):
    """Invoke with --json and return the parsed document."""
    result = runner.invoke(app, ["--json", *argv], catch_exceptions=False)
    assert result.exit_code == 0, f"dv --json {' '.join(argv)}\n{result.output}"
    buf = io.StringIO()
    with redirect_stdout(buf):
        flush()
    return json.loads(buf.getvalue())


@pytest.mark.parametrize("argv", [[f, *rest] for _, f, rest in CASES],
                         ids=[name for name, _, _ in CASES])
def test_every_command_emits_json(argv):
    """No command falls back to ASCII or emits nothing under --json."""
    doc = run_json(argv)
    assert doc is not None
    assert isinstance(doc, (list, dict))


def test_rows_come_back_as_objects():
    doc = run_json([EXPENSES, "head", "-n", "2"])
    assert [r["category"] for r in doc] == ["food", "food"]
    assert doc[0]["amount"] == 85.5


def test_dates_serialize_as_iso_strings():
    doc = run_json([EXPENSES, "head", "-n", "1"])
    assert doc[0]["date"] == "2026-01-03"


def test_query_emits_its_result_rows():
    doc = run_json([EXPENSES, "query", "SELECT count(*) AS n FROM data"])
    assert doc == [{"n": 44}]


def test_aggregation_keeps_its_column_names():
    doc = run_json([EXPENSES, "group-by", "category", "--sum", "amount"])
    assert {"category", "total"} <= set(doc[0])


def test_schema_is_an_object_not_rows():
    doc = run_json([EXPENSES, "schema"])
    assert doc["rows"] == 44
    assert {c["name"] for c in doc["columns"]} == {
        "date", "category", "amount", "method", "note"}


def test_summary_carries_the_computed_stats():
    doc = run_json([EXPENSES, "summary"])
    assert doc["rows"] == 44 and doc["columns"] == 5
    assert doc["numeric"][0]["column"] == "amount"


def test_chart_emits_data_not_glyphs():
    """A bar chart's JSON is the numbers behind it, never the ASCII."""
    doc = run_json([EXPENSES, "bar", "category"])
    assert doc[0] == {"label": "food", "value": 20}
    assert "#" not in json.dumps(doc)


def test_histogram_emits_bin_edges():
    doc = run_json([EXPENSES, "hist", "amount", "--bins", "4"])
    assert len(doc) == 4
    assert doc[0]["lo"] == 25.0 and doc[-1]["hi"] == 450.0
    assert sum(b["count"] for b in doc) == 44


def test_box_emits_the_five_numbers():
    doc = run_json([EXPENSES, "box", "amount"])
    assert doc["min"] <= doc["q1"] <= doc["median"] <= doc["q3"] <= doc["max"]


def test_computed_view_emits_its_answer_not_its_input():
    """streak's answer is the streak, not the rows it was derived from."""
    doc = run_json([EXPENSES, "streak", "--date", "date"])
    assert {"current", "best", "consistency"} <= set(doc)


def test_money_summary_emits_derived_figures():
    doc = run_json([MONEY, "money-summary"])
    assert doc["saved"] == pytest.approx(doc["income"] - doc["expense"])


def test_diff_emits_the_comparison():
    doc = run_json([EXPENSES, "diff", MONEY, "--key", "date"])
    assert {"added", "removed", "changed"} <= set(doc)


def test_multi_section_command_keys_its_sections():
    doc = run_json([EXPENSES, "report"])
    assert {"summary", "schema"} <= set(doc)


def test_where_filters_the_json_too():
    doc = run_json(["--where", "category = 'food'", EXPENSES, "table", "--limit", "50"])
    assert {r["category"] for r in doc} == {"food"}


# --- end to end: the real binary, real streams --------------------------------


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "dv.main", *args],
                          capture_output=True, text=True, timeout=120)


def test_stdout_is_only_json():
    """Nothing decorative may reach a pipe."""
    p = _cli("--json", EXPENSES, "summary")
    assert p.returncode == 0
    assert json.loads(p.stdout)["rows"] == 44


def test_ascii_is_suppressed_entirely():
    p = _cli("--json", EXPENSES, "bar", "category")
    assert "#" not in p.stdout and "---" not in p.stdout


def test_truncation_warns_on_stderr_not_stdout():
    """A script must be told it got a capped result, without corrupting the JSON."""
    p = _cli("--json", EXPENSES, "query", "SELECT * FROM data", "--limit", "5")
    assert len(json.loads(p.stdout)) == 5
    assert "emitted 5 of 44" in p.stderr


def test_errors_go_to_stderr_and_exit_nonzero():
    p = _cli("--json", EXPENSES, "bar", "no_such_column")
    assert p.returncode == 1
    assert p.stdout == ""
    assert "Unknown column" in p.stderr


def test_flag_after_the_file_explains_itself():
    """`dv f.csv summary --json` is the natural typo; it must not dead-end."""
    p = _cli(EXPENSES, "summary", "--json")
    assert p.returncode == 1
    assert "has to come before the input file" in p.stderr
    assert "dv --json <file> summary" in p.stderr


def test_command_level_where_is_not_mistaken_for_the_global_one():
    """`table --where` is a real option of its own and must still work."""
    p = _cli("--where", "amount > 10", EXPENSES,
             "table", "--where", "category = 'food'", "--limit", "50")
    assert p.returncode == 0
    assert "transport" not in p.stdout


def test_exporters_say_they_have_no_json_form(tmp_path):
    p = _cli("--json", EXPENSES, "export-md", str(tmp_path / "r.md"))
    assert p.returncode == 1
    assert "not supported by 'export-md'" in p.stderr
