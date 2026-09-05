"""End-to-end smoke tests: every registered command must run on real files.

These invoke the CLI the way a user does, so they catch failures unit tests on
the renderers cannot see - a command whose SQL is wrong, whose options collide,
or that never worked for a whole input format.

`test_every_command_is_covered` fails when a new command is added without a
case here, so the suite cannot silently fall behind the CLI.
"""

import re
import sqlite3
from pathlib import Path

import duckdb
import pytest
from typer.testing import CliRunner

import dv.main  # noqa: F401  (registers all commands on the shared app)
from dv.app import app
from dv.core.errors import DvError

runner = CliRunner()

EXPENSES = "examples/expenses.csv"
MONEY    = "examples/money.csv"
TASKS    = "examples/tasks.csv"
BOOKS    = "examples/books.csv"
STUDY    = "examples/study.csv"
SESSIONS = "examples/sessions.csv"
EXPENSES_ABS = str(Path(EXPENSES).resolve())

# (command name, argv after the input file). One entry per registered command.
CASES: list[tuple[str, str, list[str]]] = [
    # inspect
    ("schema",          EXPENSES, ["schema"]),
    ("head",            EXPENSES, ["head", "-n", "3"]),
    ("summary",         EXPENSES, ["summary"]),
    ("describe",        EXPENSES, ["describe"]),
    ("missing",         BOOKS,    ["missing"]),
    ("table",           EXPENSES, ["table", "--limit", "5", "--sort", "amount", "--desc"]),
    ("query",           EXPENSES, ["query", "SELECT category, sum(amount) t FROM data GROUP BY 1"]),
    ("report",          EXPENSES, ["report"]),
    # aggregate
    ("group-by",        EXPENSES, ["group-by", "category", "--sum", "amount", "--bar"]),
    ("pivot",           EXPENSES, ["pivot", "category", "date", "--sum", "amount"]),
    ("top",             EXPENSES, ["top", "category", "--by", "amount"]),
    # charts
    ("bar",             EXPENSES, ["bar", "category", "--sum", "amount"]),
    ("hist",            EXPENSES, ["hist", "amount", "--bins", "5"]),
    ("scatter",         STUDY,    ["scatter", "study_hours", "score"]),
    ("spark",           EXPENSES, ["spark", "amount", "--by", "date"]),
    ("composition",     EXPENSES, ["composition", "category", "--sum", "amount"]),
    ("box",             EXPENSES, ["box", "amount"]),
    ("outliers",        EXPENSES, ["outliers", "amount"]),
    ("heatmap",         EXPENSES, ["heatmap", "category", "method"]),
    ("timeline",        TASKS,    ["timeline", "--start", "start", "--end", "end",
                                   "--label", "task"]),
    ("gantt",           TASKS,    ["gantt", "--start", "start", "--end", "end", "--label", "task",
                                   "--status", "status", "--progress", "progress"]),
    ("tree",            BOOKS,    ["tree", "--path", "category/status/title"]),
    ("calendar",        EXPENSES, ["calendar", "--date", "date", "--value", "amount"]),
    # timeseries
    ("time-summary",    EXPENSES, ["time-summary", "--date", "date"]),
    ("time",            EXPENSES, ["time", "--date", "date", "--by", "month", "--sum", "amount"]),
    ("by-hour",         SESSIONS, ["by-hour", "--date", "start"]),
    ("streak",          EXPENSES, ["streak", "--date", "date"]),
    ("gaps",            EXPENSES, ["gaps", "--date", "date"]),
    ("compare-periods", EXPENSES, ["compare-periods", "--date", "date", "--value", "amount",
                                   "--period", "month"]),
    ("weekmap",         EXPENSES, ["weekmap", "--date", "date", "--value", "amount"]),
    ("rolling",         EXPENSES, ["rolling", "--date", "date", "--value", "amount",
                                   "--window", "7"]),
    ("cumulative",      EXPENSES, ["cumulative", "--date", "date", "--value", "amount"]),
    ("duration",        TASKS,    ["duration", "--start", "start", "--end", "end"]),
    ("before-after",    EXPENSES, ["before-after", "--date", "date", "--value", "amount",
                                   "--cutoff", "2026-06-15"]),
    ("countdown",       TASKS,    ["countdown", "--date", "end", "--label", "task"]),
    ("sessions",        SESSIONS, ["sessions"]),
    # money
    ("money-summary",   MONEY,    ["money-summary"]),
    ("expenses-by",     MONEY,    ["expenses-by", "category"]),
    ("income-expense",  MONEY,    ["income-expense"]),
    ("largest",         MONEY,    ["largest", "--n", "5"]),
    ("budget",          MONEY,    ["budget", "category", "--budget", "examples/budget.yml"]),
    ("burn-rate",       MONEY,    ["burn-rate", "--month", "2026-06", "--budget", "1500"]),
    ("subscriptions",   MONEY,    ["subscriptions", "--min-months", "2"]),
    ("money-report",    MONEY,    ["money-report", "--month", "2026-06"]),
    ("drill",           MONEY,    ["drill", "food", "--limit", "3"]),
    ("spend-by-weekday", MONEY,   ["spend-by-weekday"]),
    ("note-analysis",   MONEY,    ["note-analysis"]),
    ("forecast",        MONEY,    ["forecast"]),
    ("fixed-variable",  MONEY,    ["fixed-variable"]),
    # compare and export
    ("diff",            EXPENSES, ["diff", MONEY, "--key", "date"]),
    ("alias",           EXPENSES, ["alias", "money"]),
]


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


class _Result:
    r"""A CliRunner result whose `.output` carries no ANSI styling.

    Rich emits colour whenever the environment asks for it - a FORCE_COLOR in
    the shell is enough, so the same code that renders plain under CI renders
    styled on a developer's machine. Worse, the highlighter styles numbers
    *inside* a phrase, so "showing 5 of 44 rows" reaches the buffer as
    "showing \x1b[0m\x1b[1;2;36m5\x1b[0m\x1b[2m of ...". These assertions are
    about what the CLI says, not how it paints it, so styling is stripped once
    here rather than guessed at per assertion.
    """

    def __init__(self, result):
        self._result = result
        self.output = ANSI_RE.sub("", result.output)

    def __getattr__(self, name):
        return getattr(self._result, name)


def run(argv: list[str]):
    """Invoke the CLI, surfacing the real exception rather than a bare exit code."""
    result = runner.invoke(app, argv, catch_exceptions=True)
    if result.exit_code != 0:
        exc = result.exception
        raise AssertionError(
            f"dv {' '.join(argv)} exited {result.exit_code}\n"
            f"{type(exc).__name__ if exc else 'no exception'}: {exc}\n{result.output}"
        )
    return _Result(result)


@pytest.mark.parametrize("argv", [[f, *rest] for _, f, rest in CASES],
                         ids=[name for name, _, _ in CASES])
def test_command_runs(argv):
    assert run(argv).output.strip()


def test_every_command_is_covered():
    """Every command registered on the app has a smoke-test case."""
    registered = {c.name or c.callback.__name__ for c in app.registered_commands}
    covered = {name for name, _, _ in CASES} | {"export-md", "export-html"}  # covered below
    assert registered == covered, (
        f"untested commands: {sorted(registered - covered)}; "
        f"stale cases: {sorted(covered - registered)}"
    )


@pytest.mark.parametrize("cmd,ext", [("export-md", "md"), ("export-html", "html")])
def test_export_writes_file(tmp_path, cmd, ext):
    out = tmp_path / f"report.{ext}"
    run([EXPENSES, cmd, str(out)])
    assert out.stat().st_size > 0


@pytest.mark.parametrize("fmt", ["json", "ndjson", "parquet", "tsv"])
def test_other_formats_load(tmp_path, fmt):
    """Every documented file format reaches the same summary output."""
    src = tmp_path / f"data.{fmt if fmt != 'ndjson' else 'ndjson'}"
    duckdb.sql(
        f"COPY (SELECT * FROM read_csv_auto('{EXPENSES}')) TO '{src}' "
        + {"json": "(FORMAT JSON, ARRAY true)", "ndjson": "(FORMAT JSON)",
           "parquet": "(FORMAT PARQUET)", "tsv": "(HEADER, DELIMITER '\\t')"}[fmt]
    )
    assert "category" in run([str(src), "schema"]).output


def _make_sqlite(path, tables: dict[str, str]):
    conn = sqlite3.connect(path)
    for name, _ in tables.items():
        conn.execute(f"CREATE TABLE {name}(id INTEGER, label TEXT)")
        conn.execute(f"INSERT INTO {name} VALUES (1, '{name}-row')")
    conn.commit()
    conn.close()


def test_sqlite_single_table(tmp_path):
    """Regression: attached databases live in catalog 'src', not schema 'src'."""
    db = tmp_path / "one.db"
    _make_sqlite(db, {"only_table": ""})
    assert "label" in run([str(db), "schema"]).output


def test_duckdb_file(tmp_path):
    db = tmp_path / "one.duckdb"
    conn = duckdb.connect(str(db))
    conn.execute("CREATE TABLE t AS SELECT 1 AS id, 'x' AS label")
    conn.close()
    assert "label" in run([str(db), "schema"]).output


def test_sqlite_multi_table_requires_choice(tmp_path):
    db = tmp_path / "many.db"
    _make_sqlite(db, {"alpha": "", "zeta": ""})
    with pytest.raises(DvError, match="pick one with --table"):
        runner.invoke(app, [str(db), "schema"], catch_exceptions=False)


def test_sqlite_table_selection(tmp_path):
    db = tmp_path / "many.db"
    _make_sqlite(db, {"alpha": "", "zeta": ""})
    assert "alpha-row" in run(["--table", "alpha", str(db), "head"]).output


def test_sqlite_other_tables_stay_queryable(tmp_path):
    """Non-selected tables are registered too, so `query` can join across them."""
    db = tmp_path / "many.db"
    _make_sqlite(db, {"alpha": "", "zeta": ""})
    out = run(["--table", "alpha", str(db),
               "query", "SELECT z.label FROM data d JOIN zeta z ON d.id = z.id"]).output
    assert "zeta-row" in out


def test_unknown_table_name_suggests(tmp_path):
    db = tmp_path / "many.db"
    _make_sqlite(db, {"alpha": "", "zeta": ""})
    with pytest.raises(DvError) as exc:
        runner.invoke(app, ["--table", "alfa", str(db), "schema"], catch_exceptions=False)
    assert "alpha" in exc.value.hint


def test_drill_accepts_category_option():
    """--category names the value; --category-col names the column."""
    positional = run([MONEY, "drill", "food"]).output
    option     = run([MONEY, "drill", "--category", "food"]).output
    assert "food" in positional and positional == option


def test_drill_without_category_errors():
    with pytest.raises(DvError, match="No category given"):
        runner.invoke(app, [MONEY, "drill"], catch_exceptions=False)


@pytest.mark.parametrize("cmd", ["income-expense", "money-summary",
                                 "spend-by-weekday", "fixed-variable", "forecast"])
def test_money_commands_without_a_type_column(cmd):
    """A file with no income/expense column is all spending, not an error.

    expenses.csv has no `type`, and income-expense built its CASE WHEN over it
    unconditionally - so it died with a binder error on exactly the shape of
    file dv's own examples ship.
    """
    out = run([EXPENSES, cmd]).output
    assert out.strip() and "not found" not in out


# --- streamed reads -----------------------------------------------------------


def _registered_kind(argv) -> str:
    """Whether `data` ended up a VIEW or a BASE TABLE for this invocation."""
    import dv.app
    run(argv)
    conn = dv.app._source.connection
    return conn.execute(
        "SELECT table_type FROM information_schema.tables WHERE table_name = 'data'"
    ).fetchone()[0]


@pytest.mark.parametrize("argv", [
    [EXPENSES, "head", "-n", "3"],
    [EXPENSES, "table", "--limit", "5"],
    [EXPENSES, "query", "SELECT * FROM data"],
])
def test_peek_commands_use_a_view(argv):
    """A bounded read must not parse the whole file first."""
    assert _registered_kind(argv) == "VIEW"


@pytest.mark.parametrize("argv", [
    [EXPENSES, "summary"],
    [EXPENSES, "schema"],
    [EXPENSES, "bar", "category"],
    [EXPENSES, "query", "SELECT * FROM data", "--all"],
])
def test_scanning_commands_materialize(argv):
    """Anything that queries the source repeatedly still parses it once."""
    assert _registered_kind(argv) == "BASE TABLE"


def test_streamed_head_matches_materialized_head():
    """The view path returns the same rows as the table path."""
    streamed = run([EXPENSES, "head", "-n", "5"]).output
    materialized = run([EXPENSES, "query", "SELECT * FROM data LIMIT 5", "--all"]).output
    for value in ("food", "2026-01-03", "85.5"):
        assert value in streamed and value in materialized


def test_streamed_read_honours_where():
    out = run(["--where", "category = 'food'", EXPENSES, "table", "--limit", "50"]).output
    assert "food" in out and "transport" not in out


def test_streamed_read_on_attached_database(tmp_path):
    db = tmp_path / "one.db"
    _make_sqlite(db, {"only_table": ""})
    assert "only_table-row" in run([str(db), "head"]).output


def test_streamed_read_still_validates_columns():
    with pytest.raises(DvError, match="Unknown column"):
        runner.invoke(app, [EXPENSES, "table", "--sort", "amont"],
                      catch_exceptions=False)


# --- query row cap ------------------------------------------------------------


def test_query_caps_rows_and_says_so():
    """A bare select on a big file must not build a dict per row."""
    out = run([EXPENSES, "query", "SELECT * FROM data", "--limit", "5"]).output
    assert "showing 5 of 44 rows" in out


def test_query_under_the_cap_has_no_footer():
    out = run([EXPENSES, "query", "SELECT * FROM data LIMIT 3", "--limit", "50"]).output
    assert "showing" not in out


def test_query_all_disables_the_cap():
    out = run([EXPENSES, "query", "SELECT * FROM data", "--all"]).output
    assert "showing" not in out


def test_query_cap_reports_exact_total():
    out = run([EXPENSES, "query", "SELECT amount FROM data", "--limit", "2"]).output
    assert "of 44 rows" in out


def test_query_cap_survives_unwrappable_sql():
    """The total is unknown for statements that cannot be a subquery; the cap holds."""
    out = run([EXPENSES, "query", "SELECT * FROM data ORDER BY amount", "--limit", "4"]).output
    assert "showing 4" in out


def test_query_cap_respects_config_default(tmp_path, monkeypatch):
    (tmp_path / ".dv.yml").write_text("default_limit: 3\n")
    monkeypatch.chdir(tmp_path)
    out = run([EXPENSES_ABS, "query", "SELECT * FROM data"]).output
    assert "showing 3 of 44 rows" in out


# --- global --where -----------------------------------------------------------


def test_where_filters_every_command():
    """The filter is applied while `data` loads, so commands need not know it."""
    full     = run([EXPENSES, "summary"]).output
    filtered = run(["--where", "amount > 30", EXPENSES, "summary"]).output
    assert "rows" in full and "rows" in filtered
    assert full != filtered


def test_where_reaches_charts():
    """A chart command sees the filtered rows, not just `table`."""
    out = run(["--where", "category = 'food'", EXPENSES, "bar", "category"]).output
    assert "food" in out
    assert "transport" not in out


def test_where_reaches_raw_query():
    unfiltered = run([EXPENSES, "query", "SELECT count(*) AS n FROM data"]).output
    filtered   = run(["--where", "amount > 30", EXPENSES,
                      "query", "SELECT count(*) AS n FROM data"]).output
    assert unfiltered != filtered


def test_where_composes_with_table_where():
    """The global filter and `table --where` narrow together, not one or the other."""
    out = run(["--where", "amount > 10", EXPENSES,
               "table", "--where", "category = 'food'", "--limit", "50"]).output
    assert "food" in out
    assert "transport" not in out


def test_where_matching_nothing_is_not_an_error():
    assert "0" in run(["--where", "amount > 99999", EXPENSES, "summary"]).output


def test_where_matching_nothing_renders_empty_chart():
    assert "No data" in run(["--where", "amount > 99999", EXPENSES,
                             "bar", "category"]).output


def test_bad_where_names_the_flag():
    with pytest.raises(DvError) as exc:
        runner.invoke(app, ["--where", "amont > 10", EXPENSES, "summary"],
                      catch_exceptions=False)
    assert "--where" in exc.value.message


def test_where_short_flag():
    assert run(["-w", "amount > 30", EXPENSES, "summary"]).output


def test_where_on_attached_database(tmp_path):
    db = tmp_path / "one.db"
    _make_sqlite(db, {"only_table": ""})
    assert "0" in run(["--where", "id > 99", str(db), "summary"]).output


def test_export_records_the_filter(tmp_path):
    """A saved report must not look unfiltered."""
    out = tmp_path / "report.md"
    run(["--where", "amount > 30", EXPENSES, "export-md", str(out)])
    assert "amount > 30" in out.read_text()


def test_export_html_escapes_the_filter(tmp_path):
    out = tmp_path / "report.html"
    run(["--where", "amount > 30", EXPENSES, "export-html", str(out)])
    assert "amount &gt; 30" in out.read_text()


def test_unknown_column_suggests_close_match():
    with pytest.raises(DvError, match=r"categry|Did you mean"):
        runner.invoke(app, [EXPENSES, "bar", "categry"], catch_exceptions=False)


# A column name and a category value that are also HTML and Markdown syntax.
# Both come straight out of the file, so both reach the report unfiltered.
_HOSTILE = (
    "date,<script>alert(1)</script>,a|b,amount\n"
    "2026-06-01,<b>bold</b>,1,10\n"
    "2026-06-02,plain,2,20\n"
)


def test_export_html_escapes_data_from_the_file(tmp_path):
    """A column or a value is data, never markup - the report is opened in a browser."""
    src = tmp_path / "hostile.csv"
    src.write_text(_HOSTILE)
    out = tmp_path / "report.html"
    run([str(src), "export-html", str(out)])
    html = out.read_text()

    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<b>bold</b>" not in html
    assert "&lt;b&gt;bold&lt;/b&gt;" in html


def test_export_md_keeps_the_table_intact(tmp_path):
    """A pipe in a column name would otherwise split the cell and shear the table."""
    src = tmp_path / "hostile.csv"
    src.write_text(_HOSTILE)
    out = tmp_path / "report.md"
    run([str(src), "export-md", str(out)])

    schema_rows = [
        line for line in out.read_text().splitlines()
        if line.startswith("|") and "---" not in line
    ]
    # Every row of both tables has the same cell count as its header.
    widths = {line.count("|") - line.count(r"\|") for line in schema_rows}
    assert widths == {5, 7}, widths
