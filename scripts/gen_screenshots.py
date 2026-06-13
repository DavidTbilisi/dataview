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
    for mod in (t, s, c, h, tl, hm, tr, ex):
        if hasattr(mod, "console"):
            mod.console = new_console


def save(console: Console, name: str):
    out = Path("docs/screenshots") / f"{name}.svg"
    console.save_svg(str(out), title=f"dv {name}")
    print(f"  saved {out}")


# ── imports after sys.path is set ────────────────────────────────────────────

from dv.core.detect import make_datasource
from dv.core.query import run_query, run_table_query
from dv.core.schema import get_schema
from dv.core.stats import get_summary
from dv.render.table import render_table
from dv.render.summary import render_schema, render_summary, render_missing
from dv.render.charts import render_bar
from dv.render.histogram import render_histogram
from dv.render.timeline import render_timeline

EXPENSES = Path("examples/expenses.csv")
TASKS = Path("examples/tasks.csv")
BOOKS = Path("examples/books.csv")


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


if __name__ == "__main__":
    print("Generating screenshots...")
    shot_schema()
    shot_summary()
    shot_head()
    shot_query()
    shot_bar()
    shot_hist()
    shot_timeline()
    shot_groupby()
    shot_books()
    print("Done.")
