"""Generate SVG screenshots from real dv command output."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console

# ── helpers ──────────────────────────────────────────────────────────────────

def make_console() -> Console:
    return Console(record=True, width=80, highlight=False, force_terminal=True)


def patch_consoles(new_console: Console):
    """Replace every module-level `console` in render/* with the recording one."""
    import dv.render.table as t
    import dv.render.summary as s
    import dv.render.charts as c
    import dv.render.histogram as h
    import dv.render.timeline as tl
    import dv.render.heatmap as hm
    import dv.render.tree as tr
    import dv.render.export as ex
    import dv.render.gantt as g
    import dv.render.time_views as tv
    import dv.render.money as mo
    for mod in (t, s, c, h, tl, hm, tr, ex, g, tv, mo):
        if hasattr(mod, "console"):
            mod.console = new_console


def save(console: Console, name: str):
    out = Path("docs/screenshots") / f"{name}.svg"
    console.save_svg(str(out), title=f"dv {name}")
    print(f"  saved {out}")


# ── imports after sys.path is set ────────────────────────────────────────────

import duckdb

from dv.core.detect import make_datasource
from dv.core.query import run_query, run_table_query
from dv.core.schema import get_schema
from dv.core.stats import get_summary
from dv.render.table import render_table
from dv.render.summary import render_schema, render_summary, render_missing
from dv.render.charts import render_bar
from dv.render.histogram import render_histogram
from dv.render.timeline import render_timeline
from dv.render.gantt import render_gantt
from dv.render.time_views import render_weekmap, render_rolling, render_cumulative
from dv.render.money import (
    render_money_summary,
    render_expenses_by,
    render_income_expense,
    render_burn_rate,
    render_subscriptions,
)

EXPENSES = Path("examples/expenses.csv")
TASKS    = Path("examples/tasks.csv")
BOOKS    = Path("examples/books.csv")
MONEY    = Path("examples/money.csv")


def _money_con():
    con = duckdb.connect()
    con.execute(f"CREATE VIEW data AS SELECT * FROM read_csv_auto('{MONEY}')")
    return con


# ── screenshots ──────────────────────────────────────────────────────────────

def shot_schema():
    c = make_console(); patch_consoles(c)
    ds = make_datasource(EXPENSES)
    render_schema(get_schema(ds))
    save(c, "schema")


def shot_summary():
    c = make_console(); patch_consoles(c)
    ds = make_datasource(EXPENSES)
    render_summary(get_summary(ds))
    save(c, "summary")


def shot_head():
    c = make_console(); patch_consoles(c)
    ds = make_datasource(EXPENSES)
    result = run_table_query(ds, limit=8)
    render_table(result, title="expenses.csv — first 8 rows")
    save(c, "head")


def shot_query():
    c = make_console(); patch_consoles(c)
    ds = make_datasource(EXPENSES)
    sql = "SELECT category, sum(amount) AS total FROM data GROUP BY category ORDER BY total DESC"
    result = run_query(ds, sql)
    render_table(result, title="Query: expenses.csv")
    save(c, "query")


def shot_bar():
    c = make_console(); patch_consoles(c)
    ds = make_datasource(EXPENSES)
    sql = "SELECT category, count(*) as count FROM data GROUP BY category ORDER BY count DESC"
    result = run_query(ds, sql)
    rows = [(r["category"], r["count"]) for r in result.rows]
    render_bar(rows, title="category", width=40)
    save(c, "bar")


def shot_hist():
    c = make_console(); patch_consoles(c)
    ds = make_datasource(EXPENSES)
    sql = "SELECT amount FROM data WHERE amount IS NOT NULL"
    result = run_query(ds, sql)
    values = [float(r["amount"]) for r in result.rows]
    render_histogram(values, title="amount", bins=8, width=40)
    save(c, "hist")


def shot_timeline():
    c = make_console(); patch_consoles(c)
    ds = make_datasource(TASKS)
    sql = 'SELECT task, "start", "end" FROM data ORDER BY "start"'
    result = run_query(ds, sql)
    render_timeline(result.rows, start_col="start", end_col="end", label_col="task", width=60)
    save(c, "timeline")


def shot_groupby():
    c = make_console(); patch_consoles(c)
    ds = make_datasource(EXPENSES)
    sql = "SELECT category, sum(amount) AS total FROM data GROUP BY category ORDER BY total DESC"
    result = run_query(ds, sql)
    render_table(result, title="group-by category --sum amount")
    rows = [(r["category"], r["total"]) for r in result.rows]
    render_bar(rows, title="category totals", width=40)
    save(c, "groupby")


def shot_books():
    c = make_console(); patch_consoles(c)
    ds = make_datasource(BOOKS)
    sql = "SELECT status, count(*) as count FROM data GROUP BY status ORDER BY count DESC"
    result = run_query(ds, sql)
    rows = [(r["status"], r["count"]) for r in result.rows]
    render_bar(rows, title="books by status", width=40)
    save(c, "books_bar")


def shot_gantt():
    c = make_console(); patch_consoles(c)
    con = duckdb.connect()
    con.execute(f"CREATE VIEW data AS SELECT * FROM read_csv_auto('{TASKS}')")
    rows = con.execute(
        'SELECT task, "start"::DATE AS start, "end"::DATE AS end, status, progress FROM data ORDER BY "start"'
    ).fetchall()
    rows_dict = [
        {"task": r[0], "start": r[1], "end": r[2], "status": r[3], "progress": r[4]}
        for r in rows
    ]
    render_gantt(rows_dict, "start", "end", "task", status_col="status", progress_col="progress", width=40)
    save(c, "gantt")


def shot_weekmap():
    c = make_console(); patch_consoles(c)
    con = _money_con()
    rows = con.execute(
        "SELECT date::DATE AS date, amount FROM data WHERE type='expense' ORDER BY date"
    ).fetchall()
    rows_dict = [{"date": r[0], "amount": r[1]} for r in rows]
    render_weekmap(rows_dict, "date", "amount", title="EXPENSES WEEKMAP")
    save(c, "weekmap")


def shot_money_summary():
    c = make_console(); patch_consoles(c)
    con = _money_con()
    income      = con.execute("SELECT SUM(amount) FROM data WHERE type='income'").fetchone()[0] or 0
    expense     = con.execute("SELECT SUM(amount) FROM data WHERE type='expense'").fetchone()[0] or 0
    tx_count    = con.execute("SELECT COUNT(*) FROM data WHERE type='expense'").fetchone()[0] or 0
    avg_expense = con.execute("SELECT AVG(amount) FROM data WHERE type='expense'").fetchone()[0] or 0
    max_expense = con.execute("SELECT MAX(amount) FROM data WHERE type='expense'").fetchone()[0] or 0
    dr          = con.execute("SELECT MIN(date), MAX(date) FROM data").fetchone()
    date_range  = (str(dr[0])[:10], str(dr[1])[:10]) if dr else None
    accounts    = [r[0] for r in con.execute("SELECT DISTINCT account FROM data ORDER BY account").fetchall()]
    render_money_summary(income, expense, tx_count, avg_expense, max_expense, date_range, accounts)
    save(c, "money_summary")


def shot_expenses_by():
    c = make_console(); patch_consoles(c)
    con = _money_con()
    rows = con.execute(
        "SELECT category, SUM(amount) AS total FROM data WHERE type='expense' GROUP BY category ORDER BY total DESC"
    ).fetchall()
    items = [(r[0], float(r[1])) for r in rows]
    render_expenses_by(items, title="EXPENSES BY CATEGORY")
    save(c, "expenses_by")


def shot_income_expense():
    c = make_console(); patch_consoles(c)
    con = _money_con()
    rows = con.execute("""
        SELECT strftime(date::DATE, '%Y-%m') AS period,
               SUM(CASE WHEN type='income'  THEN amount ELSE 0 END) AS income,
               SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) AS expense
        FROM data
        GROUP BY period
        ORDER BY period
    """).fetchall()
    ie_rows = [{"period": r[0], "income": float(r[1]), "expense": float(r[2])} for r in rows]
    render_income_expense(ie_rows, title="INCOME VS EXPENSE (monthly)")
    save(c, "income_expense")


def shot_burn_rate():
    c = make_console(); patch_consoles(c)
    con = _money_con()
    spent = con.execute(
        "SELECT SUM(amount) FROM data WHERE type='expense' AND strftime(date::DATE,'%Y-%m')='2026-06'"
    ).fetchone()[0] or 0
    render_burn_rate(
        spent=float(spent),
        budget=1500.0,
        days_passed=13,
        days_total=30,
        month_label="2026-06",
    )
    save(c, "burn_rate")


def shot_subscriptions():
    c = make_console(); patch_consoles(c)
    con = _money_con()
    rows = con.execute("""
        SELECT note,
               AVG(amount)              AS amount,
               COUNT(DISTINCT strftime(date::DATE,'%Y-%m')) AS months
        FROM data
        WHERE type='expense'
        GROUP BY note
        HAVING COUNT(DISTINCT strftime(date::DATE,'%Y-%m')) >= 2
        ORDER BY amount DESC
    """).fetchall()
    items = [{"name": r[0], "amount": float(r[1]), "months": int(r[2])} for r in rows]
    render_subscriptions(items, title="SUBSCRIPTIONS")
    save(c, "subscriptions")


if __name__ == "__main__":
    print("Generating screenshots...")
    # Core
    shot_schema()
    shot_summary()
    shot_head()
    shot_query()
    shot_bar()
    shot_hist()
    shot_timeline()
    shot_groupby()
    shot_books()
    # New
    shot_gantt()
    shot_weekmap()
    shot_money_summary()
    shot_expenses_by()
    shot_income_expense()
    shot_burn_rate()
    shot_subscriptions()
    print("Done.")
