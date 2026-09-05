"""Personal-finance commands."""

import re

from pathlib import Path
from typing import Optional

import typer

from dv.app import (
    app,
    ds as _ds,
    limit_or_default,
)
from dv.core.errors import DvError
from dv.core.query import run_query, require_columns
from dv.core.schema import get_schema
from dv.core.sql import lit, period_expr
from dv.render.common import fmt_date
from dv.render.theme import console
from dv.render.table import render_table
from dv.render.money import (
    render_money_summary, render_expenses_by, render_income_expense,
    render_budget, render_burn_rate, render_savings_rate,
    render_subscriptions, render_money_report,
    render_drill, render_spend_by_weekday, render_remaining,
    render_note_analysis, render_forecast, render_fixed_variable,
)


def _parse_month(month: str) -> tuple[int, int]:
    """Parse a YYYY-MM option value."""
    m = re.fullmatch(r"(\d{4})-(\d{2})", str(month).strip())
    if not m:
        raise DvError(f"Invalid --month: {month!r}", hint="Expected YYYY-MM, e.g. 2026-06")
    year, mon = int(m.group(1)), int(m.group(2))
    if not 1 <= mon <= 12:
        raise DvError(f"Invalid month number in {month!r}", hint="Month must be 01-12")
    return year, mon


def _has_col(schema_info, col_name: str) -> bool:
    return any(c.name == col_name for c in schema_info.columns)


def _load_budget(path: Path) -> dict[str, float]:
    """Read a `category: amount` YAML file, or explain why it could not be read."""
    import yaml

    if not path.exists():
        raise DvError(f"Budget file not found: {path}",
                      hint="Expected a YAML file of `category: amount` entries.")
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise DvError(f"Could not parse {path}", hint=str(e).splitlines()[0])
    if not isinstance(data, dict):
        raise DvError(f"{path} must be a mapping of category to amount")
    out = {}
    for key, value in data.items():
        try:
            out[str(key)] = float(value)
        except (TypeError, ValueError):
            raise DvError(f"Budget for {key!r} is not a number: {value!r}")
    return out


@app.command(name="money-summary")
def money_summary(
    type_col:    str = typer.Option("type",    "--type",    help="Transaction type column"),
    amount_col:  str = typer.Option("amount",  "--amount",  help="Amount column"),
    date_col:    str = typer.Option("date",    "--date",    help="Date column"),
    income_val:  str = typer.Option("income",  "--income",  help="Value meaning income"),
    expense_val: str = typer.Option("expense", "--expense", help="Value meaning expense"),
):
    """Show money summary: income, expenses, savings rate."""
    ds          = _ds()
    require_columns(ds, amount_col, date_col)
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)

    if has_type:
        r_inc = run_query(ds, f"""
            SELECT COALESCE(sum("{amount_col}"), 0) AS total
            FROM data WHERE "{type_col}" = {lit(income_val)}
        """)
        r_exp = run_query(ds, f"""
            SELECT COALESCE(sum("{amount_col}"), 0)  AS total,
                   count(*)                           AS cnt,
                   COALESCE(avg("{amount_col}"), 0)  AS avg_val,
                   COALESCE(max("{amount_col}"), 0)  AS max_val
            FROM data WHERE "{type_col}" = {lit(expense_val)}
        """)
        income   = float(r_inc.rows[0]["total"])
        expense  = float(r_exp.rows[0]["total"])
        tx_count = int(r_exp.rows[0]["cnt"])
        avg_exp  = float(r_exp.rows[0]["avg_val"])
        max_exp  = float(r_exp.rows[0]["max_val"])
    else:
        r = run_query(ds, f"""
            SELECT COALESCE(sum("{amount_col}"), 0)  AS total,
                   count(*)                           AS cnt,
                   COALESCE(avg("{amount_col}"), 0)  AS avg_val,
                   COALESCE(max("{amount_col}"), 0)  AS max_val
            FROM data WHERE "{amount_col}" IS NOT NULL
        """)
        income   = 0.0
        expense  = float(r.rows[0]["total"])
        tx_count = int(r.rows[0]["cnt"])
        avg_exp  = float(r.rows[0]["avg_val"])
        max_exp  = float(r.rows[0]["max_val"])

    r_dates = run_query(ds, f'SELECT min("{date_col}") AS mn, max("{date_col}") AS mx FROM data')
    mn_d, mx_d = r_dates.rows[0]["mn"], r_dates.rows[0]["mx"]
    date_range = (fmt_date(mn_d), fmt_date(mx_d)) if mn_d else None

    accounts: list[str] = []
    if _has_col(schema_info, "account"):
        r_acc = run_query(ds, "SELECT DISTINCT account FROM data WHERE account IS NOT NULL ORDER BY account")
        accounts = [str(r["account"]) for r in r_acc.rows]

    render_money_summary(income, expense, tx_count, avg_exp, max_exp, date_range, accounts or None)


@app.command(name="expenses-by")
def expenses_by(
    column:      str = typer.Argument(..., help="Column to group by"),
    type_col:    str = typer.Option("type",    "--type"),
    amount_col:  str = typer.Option("amount",  "--amount"),
    expense_val: str = typer.Option("expense", "--expense"),
    limit:       Optional[int] = typer.Option(None, "--limit", "-l"),
):
    """Show expenses broken down by a column (bar chart with %)."""
    ds          = _ds()
    limit = limit_or_default(limit, 15)
    require_columns(ds, column, amount_col)
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)
    where       = f'WHERE "{type_col}" = {lit(expense_val)}' if has_type else f'WHERE "{amount_col}" IS NOT NULL'
    sql         = f'SELECT "{column}", sum("{amount_col}") AS total FROM data {where} GROUP BY "{column}" ORDER BY total DESC LIMIT {limit}'
    result      = run_query(ds, sql)
    items       = [(str(r[column]), float(r["total"])) for r in result.rows]
    render_expenses_by(items, title=f"EXPENSES BY {column.upper()}")


@app.command(name="income-expense")
def income_expense_cmd(
    by:          str = typer.Option("month",   "--by",      help="day|week|month|year"),
    type_col:    str = typer.Option("type",    "--type"),
    amount_col:  str = typer.Option("amount",  "--amount"),
    date_col:    str = typer.Option("date",    "--date"),
    income_val:  str = typer.Option("income",  "--income"),
    expense_val: str = typer.Option("expense", "--expense"),
):
    """Show income vs expense by time period."""
    ds = _ds()
    require_columns(ds, amount_col, date_col)
    p_expr = period_expr(date_col, by)
    sql = f"""
        SELECT {p_expr} AS period,
               sum(CASE WHEN "{type_col}" = {lit(income_val)}  THEN "{amount_col}" ELSE 0 END) AS income,
               sum(CASE WHEN "{type_col}" = {lit(expense_val)} THEN "{amount_col}" ELSE 0 END) AS expense
        FROM data WHERE "{date_col}" IS NOT NULL
        GROUP BY {p_expr} ORDER BY {p_expr}
    """
    result = run_query(ds, sql)
    rows   = [{"period": str(r["period"]), "income": r["income"], "expense": r["expense"]}
              for r in result.rows]
    render_income_expense(rows)


@app.command()
def largest(
    amount_col:  str = typer.Option("amount",  "--amount"),
    type_col:    str = typer.Option("type",    "--type"),
    expense_val: str = typer.Option("expense", "--expense"),
    limit:       Optional[int] = typer.Option(None, "--limit", "-l", "--n"),
):
    """Show the largest transactions sorted by amount."""
    ds          = _ds()
    limit = limit_or_default(limit, 10)
    require_columns(ds, amount_col)
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)
    where       = f'WHERE "{type_col}" = {lit(expense_val)}' if has_type else f'WHERE "{amount_col}" IS NOT NULL'
    result      = run_query(ds, f'SELECT * FROM data {where} ORDER BY "{amount_col}" DESC LIMIT {limit}')
    render_table(result, title="LARGEST TRANSACTIONS")


@app.command()
def budget(
    column:      str  = typer.Argument(..., help="Category column"),
    budget_file: Path = typer.Option(..., "--budget", help="YAML file with category budgets"),
    type_col:    str  = typer.Option("type",    "--type"),
    amount_col:  str  = typer.Option("amount",  "--amount"),
    expense_val: str  = typer.Option("expense", "--expense"),
):
    """Compare actual spending against a YAML budget file."""
    ds          = _ds()
    require_columns(ds, column, amount_col)
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)
    where       = f'WHERE "{type_col}" = {lit(expense_val)}' if has_type else f'WHERE "{amount_col}" IS NOT NULL'
    sql         = f'SELECT "{column}", sum("{amount_col}") AS total FROM data {where} GROUP BY "{column}" ORDER BY total DESC'
    result      = run_query(ds, sql)
    items       = [(str(r[column]), float(r["total"])) for r in result.rows]
    budget_dict = _load_budget(budget_file)
    render_budget(items, budget_dict)


@app.command(name="burn-rate")
def burn_rate(
    budget_amount: float        = typer.Option(..., "--budget", help="Monthly budget"),
    month:         str          = typer.Option("",  "--month",  help="Month as YYYY-MM (default: latest in data)"),
    type_col:      str          = typer.Option("type",    "--type"),
    amount_col:    str          = typer.Option("amount",  "--amount"),
    date_col:      str          = typer.Option("date",    "--date"),
    expense_val:   str          = typer.Option("expense", "--expense"),
):
    """Show spending pace vs budget for a month."""
    from datetime import date as _date
    from calendar import monthrange
    ds          = _ds()
    require_columns(ds, amount_col, date_col)
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)

    if not month:
        r = run_query(ds, f'SELECT max("{date_col}") AS mx FROM data')
        month = str(r.rows[0]["mx"])[:7]

    year, mon  = _parse_month(month)
    days_total = monthrange(year, mon)[1]
    today      = _date.today()
    if today.year == year and today.month == mon:
        days_passed = today.day
    else:
        days_passed = days_total

    type_filter = f' AND "{type_col}" = {lit(expense_val)}' if has_type else ''
    r_spent = run_query(ds, f"""
        SELECT COALESCE(sum("{amount_col}"), 0) AS total FROM data
        WHERE strftime("{date_col}"::DATE, '%Y-%m') = {lit(month)}{type_filter}
    """)
    spent = float(r_spent.rows[0]["total"])

    month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    render_burn_rate(spent, budget_amount, days_passed, days_total,
                     f"{month_names[mon - 1]} {year}")


@app.command(name="savings-rate")
def savings_rate_cmd(
    by:          str = typer.Option("month",   "--by"),
    type_col:    str = typer.Option("type",    "--type"),
    amount_col:  str = typer.Option("amount",  "--amount"),
    date_col:    str = typer.Option("date",    "--date"),
    income_val:  str = typer.Option("income",  "--income"),
    expense_val: str = typer.Option("expense", "--expense"),
):
    """Show savings rate trend by time period."""
    ds = _ds()
    require_columns(ds, amount_col, date_col)
    p_expr = period_expr(date_col, by)
    sql = f"""
        SELECT {p_expr} AS period,
               sum(CASE WHEN "{type_col}" = {lit(income_val)}  THEN "{amount_col}" ELSE 0 END) AS income,
               sum(CASE WHEN "{type_col}" = {lit(expense_val)} THEN "{amount_col}" ELSE 0 END) AS expense
        FROM data WHERE "{date_col}" IS NOT NULL
        GROUP BY {p_expr} ORDER BY {p_expr}
    """
    result = run_query(ds, sql)
    rows   = [{"period": str(r["period"]), "income": r["income"], "expense": r["expense"]}
              for r in result.rows]
    render_savings_rate(rows)


@app.command()
def subscriptions(
    type_col:    str = typer.Option("type",    "--type"),
    amount_col:  str = typer.Option("amount",  "--amount"),
    date_col:    str = typer.Option("date",    "--date"),
    note_col:    str = typer.Option("note",    "--note",    help="Column to group recurring by"),
    expense_val: str = typer.Option("expense", "--expense"),
    min_months:  int = typer.Option(2, "--min-months", help="Minimum months to count as recurring"),
):
    """Detect recurring payments (same name, similar amount, multiple months)."""
    ds          = _ds()
    require_columns(ds, amount_col, date_col, note_col)
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)
    type_filter = f' AND "{type_col}" = {lit(expense_val)}' if has_type else ''
    sql = f"""
        WITH monthly AS (
            SELECT
                "{note_col}" AS name,
                strftime("{date_col}"::DATE, '%Y-%m') AS month,
                avg("{amount_col}") AS avg_amount
            FROM data
            WHERE "{note_col}" IS NOT NULL{type_filter}
            GROUP BY "{note_col}", strftime("{date_col}"::DATE, '%Y-%m')
        )
        SELECT name, count(DISTINCT month) AS months, avg(avg_amount) AS amount
        FROM monthly
        GROUP BY name
        HAVING count(DISTINCT month) >= {min_months}
        ORDER BY months DESC, amount DESC
    """
    result = run_query(ds, sql)
    items  = [{"name": r["name"], "amount": r["amount"], "months": r["months"]}
              for r in result.rows]
    render_subscriptions(items)


@app.command(name="money-report")
def money_report(
    month:        str           = typer.Option("",         "--month",    help="Month YYYY-MM (default: all)"),
    type_col:     str           = typer.Option("type",     "--type"),
    amount_col:   str           = typer.Option("amount",   "--amount"),
    date_col:     str           = typer.Option("date",     "--date"),
    category_col: str           = typer.Option("category", "--category-col"),
    income_val:   str           = typer.Option("income",   "--income"),
    expense_val:  str           = typer.Option("expense",  "--expense"),
    budget_file:  Optional[Path]= typer.Option(None,       "--budget"),
):
    """Full money report: summary, expenses by category, cashflow."""
    ds          = _ds()
    require_columns(ds, amount_col, date_col, category_col)
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)

    month_filter     = f' AND strftime("{date_col}"::DATE, \'%Y-%m\') = {lit(month)}' if month else ''
    month_filter_pre = f' WHERE strftime("{date_col}"::DATE, \'%Y-%m\') = {lit(month)}' if month else ' WHERE 1=1'
    type_exp_filter  = f'{month_filter_pre} AND "{type_col}" = {lit(expense_val)}' if has_type else f'{month_filter_pre} AND "{amount_col}" IS NOT NULL'

    if has_type:
        r_inc = run_query(ds, f'SELECT COALESCE(sum("{amount_col}"), 0) AS total FROM data WHERE "{type_col}" = {lit(income_val)}{month_filter}')
        r_exp = run_query(ds, f'SELECT COALESCE(sum("{amount_col}"), 0) AS total FROM data WHERE "{type_col}" = {lit(expense_val)}{month_filter}')
        income  = float(r_inc.rows[0]["total"])
        expense = float(r_exp.rows[0]["total"])
    else:
        r = run_query(ds, f'SELECT COALESCE(sum("{amount_col}"), 0) AS total FROM data WHERE "{amount_col}" IS NOT NULL{month_filter}')
        income  = 0.0
        expense = float(r.rows[0]["total"])

    r_cat     = run_query(ds, f'SELECT "{category_col}", sum("{amount_col}") AS total FROM data{type_exp_filter} GROUP BY "{category_col}" ORDER BY total DESC LIMIT 15')
    exp_by_cat = [(str(r[category_col]), float(r["total"])) for r in r_cat.rows]

    r_dates   = run_query(ds, f'SELECT min("{date_col}") AS mn, max("{date_col}") AS mx FROM data')
    mn_d, mx_d = r_dates.rows[0]["mn"], r_dates.rows[0]["mx"]
    date_range = (fmt_date(mn_d), fmt_date(mx_d)) if mn_d else None

    r_large = run_query(ds, f'SELECT "{date_col}", "{category_col}", "{amount_col}" FROM data{type_exp_filter} ORDER BY "{amount_col}" DESC LIMIT 5')

    budget_dict = _load_budget(budget_file) if budget_file else None

    render_money_report(income, expense, exp_by_cat, date_range,
                        r_large.rows, budget_dict, month_label=month)


@app.command()
def drill(
    category:      Optional[str] = typer.Argument(None, help="Category value to drill into"),
    category_opt:  Optional[str] = typer.Option(None,   "--category",
                                                help="Category value (same as the argument)"),
    category_col:  str = typer.Option("category",    "--category-col",
                                      help="Column holding the category"),
    subcat_col:    str = typer.Option("subcategory", "--subcat"),
    amount_col:    str = typer.Option("amount",      "--amount"),
    date_col:      str = typer.Option("date",        "--date"),
    type_col:      str = typer.Option("type",        "--type"),
    expense_val:   str = typer.Option("expense",     "--expense"),
    n:             int = typer.Option(5,             "--n", "--limit", "-l",
                                      help="Top N largest transactions"),
):
    """Drill into a single category: subcategory breakdown + largest transactions."""
    ds          = _ds()
    # `dv money.csv drill --category food` reads as naturally as the positional
    # form, so accept both rather than failing on a plausible invocation.
    category    = category_opt if category_opt is not None else category
    if category is None:
        raise DvError("No category given",
                      hint="Usage: dv <file> drill <category>")
    require_columns(ds, category_col, amount_col, date_col)
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)
    has_subcat  = _has_col(schema_info, subcat_col)

    type_filter = f' AND "{type_col}" = {lit(expense_val)}' if has_type else ''
    where       = f'WHERE "{category_col}" = {lit(category)}{type_filter}'

    r_stats  = run_query(ds, f'SELECT COUNT(*) AS cnt, SUM("{amount_col}") AS total, AVG("{amount_col}") AS avg FROM data {where}')
    stats    = r_stats.rows[0] if r_stats.rows else {}
    total    = float(stats.get("total") or 0)
    tx_count = int(stats.get("cnt") or 0)
    avg      = float(stats.get("avg") or 0)

    subcats: list[tuple[str, float]] = []
    if has_subcat:
        r_sub  = run_query(ds, f'SELECT "{subcat_col}", SUM("{amount_col}") AS t FROM data {where} GROUP BY "{subcat_col}" ORDER BY t DESC')
        subcats = [(str(r[subcat_col]), float(r["t"])) for r in r_sub.rows]

    r_large  = run_query(ds, f'SELECT "{date_col}", "{subcat_col if has_subcat else category_col}", "{amount_col}" FROM data {where} ORDER BY "{amount_col}" DESC LIMIT {n}')
    render_drill(category, total, tx_count, avg, subcats, r_large.rows)


@app.command(name="spend-by-weekday")
def spend_by_weekday(
    date_col:    str = typer.Option("date",    "--date"),
    amount_col:  str = typer.Option("amount",  "--amount"),
    type_col:    str = typer.Option("type",    "--type"),
    expense_val: str = typer.Option("expense", "--expense"),
    mode:        str = typer.Option("total",   "--mode",   help="total or avg"),
):
    """Average or total spending by day of week (Mon–Sun)."""
    ds          = _ds()
    require_columns(ds, date_col, amount_col)
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)
    type_filter = f' AND "{type_col}" = {lit(expense_val)}' if has_type else ''

    agg = f'SUM("{amount_col}")' if mode == "total" else f'AVG("{amount_col}")'
    sql = f"""
        SELECT dayname("{date_col}"::DATE) AS weekday,
               dayofweek("{date_col}"::DATE) AS dow,
               {agg} AS val
        FROM data
        WHERE "{amount_col}" IS NOT NULL{type_filter}
        GROUP BY weekday, dow
        ORDER BY dow
    """
    result = run_query(ds, sql)
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_abbr  = {"Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed", "Thursday": "Thu",
                 "Friday": "Fri", "Saturday": "Sat", "Sunday": "Sun"}
    row_map   = {r["weekday"]: float(r["val"] or 0) for r in result.rows}
    items     = [(day_abbr.get(d, d[:3]), row_map.get(d, 0.0)) for d in day_order if d in row_map]
    title     = f"SPENDING BY WEEKDAY ({mode})"
    render_spend_by_weekday(items, title=title)


@app.command()
def remaining(
    budget:      float = typer.Option(...,       "--budget", help="Total budget for the month"),
    month:       str   = typer.Option("",        "--month",  help="Month YYYY-MM (default: current)"),
    date_col:    str   = typer.Option("date",    "--date"),
    amount_col:  str   = typer.Option("amount",  "--amount"),
    type_col:    str   = typer.Option("type",    "--type"),
    expense_val: str   = typer.Option("expense", "--expense"),
):
    """Budget remaining and safe daily spend."""
    from calendar import monthrange
    from datetime import date

    ds          = _ds()
    require_columns(ds, date_col, amount_col)
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)

    if not month:
        month = date.today().strftime("%Y-%m")

    type_filter = f' AND "{type_col}" = {lit(expense_val)}' if has_type else ''
    sql = f"""
        SELECT COALESCE(SUM("{amount_col}"), 0) AS spent
        FROM data
        WHERE strftime("{date_col}"::DATE, '%Y-%m') = {lit(month)}{type_filter}
    """
    spent = float(run_query(ds, sql).rows[0]["spent"])

    y, m     = _parse_month(month)
    days_total  = monthrange(y, m)[1]
    today       = date.today()
    if today.year == y and today.month == m:
        days_passed = today.day
    else:
        days_passed = days_total

    render_remaining(spent, budget, days_passed, days_total, month_label=month)


@app.command(name="note-analysis")
def note_analysis(
    note_col:    str = typer.Option("note",    "--note",    help="Merchant/note column"),
    amount_col:  str = typer.Option("amount",  "--amount"),
    type_col:    str = typer.Option("type",    "--type"),
    expense_val: str = typer.Option("expense", "--expense"),
    n:           int = typer.Option(20,        "--n", "--limit", "-l",
                                      help="Top N merchants"),
):
    """Group by merchant/note column: count, total, average."""
    ds          = _ds()
    require_columns(ds, note_col, amount_col)
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)
    type_filter = f' AND "{type_col}" = {lit(expense_val)}' if has_type else ''

    sql = f"""
        SELECT "{note_col}" AS merchant,
               COUNT(*) AS count,
               SUM("{amount_col}") AS total,
               AVG("{amount_col}") AS avg
        FROM data
        WHERE "{amount_col}" IS NOT NULL{type_filter}
        GROUP BY "{note_col}"
        ORDER BY total DESC
        LIMIT {n}
    """
    rows  = run_query(ds, sql).rows
    items = [{"merchant": r["merchant"], "count": r["count"],
              "total": float(r["total"] or 0), "avg": float(r["avg"] or 0)}
             for r in rows]
    render_note_analysis(items)


@app.command()
def forecast(
    months_back: int = typer.Option(3,        "--history", help="Months of history to average"),
    months_fwd:  int = typer.Option(3,        "--forward", help="Months to project forward"),
    date_col:    str = typer.Option("date",   "--date"),
    amount_col:  str = typer.Option("amount", "--amount"),
    type_col:    str = typer.Option("type",   "--type"),
    income_val:  str = typer.Option("income", "--income"),
    expense_val: str = typer.Option("expense","--expense"),
):
    """Project future cashflow based on rolling average of recent months."""
    from datetime import date

    ds          = _ds()
    require_columns(ds, date_col, amount_col)
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)

    if has_type:
        sql = f"""
            SELECT strftime("{date_col}"::DATE, '%Y-%m') AS period,
                   SUM(CASE WHEN "{type_col}" = {lit(income_val)}  THEN "{amount_col}" ELSE 0 END) AS income,
                   SUM(CASE WHEN "{type_col}" = {lit(expense_val)} THEN "{amount_col}" ELSE 0 END) AS expense
            FROM data
            GROUP BY period
            ORDER BY period DESC
            LIMIT {months_back}
        """
    else:
        sql = f"""
            SELECT strftime("{date_col}"::DATE, '%Y-%m') AS period,
                   0 AS income,
                   SUM("{amount_col}") AS expense
            FROM data
            GROUP BY period
            ORDER BY period DESC
            LIMIT {months_back}
        """

    hist_rows = run_query(ds, sql).rows
    if not hist_rows:
        console.print("[dim]No data[/dim]")
        return

    historical = [{"period": r["period"], "income": float(r["income"] or 0),
                   "expense": float(r["expense"] or 0)} for r in hist_rows]

    avg_inc = sum(r["income"] for r in historical) / len(historical)
    avg_exp = sum(r["expense"] for r in historical) / len(historical)

    # Project forward from next month
    today = date.today()
    y, m  = today.year, today.month
    projected = []
    for _ in range(months_fwd):
        m += 1
        if m > 12:
            m  = 1
            y += 1
        projected.append({"period": f"{y}-{m:02d}", "income": avg_inc, "expense": avg_exp})

    render_forecast(historical[::-1], projected)


@app.command(name="fixed-variable")
def fixed_variable(
    date_col:    str   = typer.Option("date",    "--date"),
    amount_col:  str   = typer.Option("amount",  "--amount"),
    category_col:str   = typer.Option("category","--category-col"),
    type_col:    str   = typer.Option("type",    "--type"),
    expense_val: str   = typer.Option("expense", "--expense"),
    cv_threshold:float = typer.Option(0.15,      "--threshold",
                                      help="Coefficient of variation threshold for 'fixed'"),
):
    """Classify expense categories as fixed (low variance) vs variable (high variance)."""
    ds          = _ds()
    require_columns(ds, date_col, amount_col, category_col)
    schema_info = get_schema(ds)
    has_type    = _has_col(schema_info, type_col)
    type_filter = f' AND "{type_col}" = {lit(expense_val)}' if has_type else ''

    sql = f"""
        SELECT "{category_col}" AS category,
               AVG(monthly_total)   AS avg_monthly,
               STDDEV(monthly_total) AS stddev_monthly
        FROM (
            SELECT "{category_col}",
                   strftime("{date_col}"::DATE, '%Y-%m') AS month,
                   SUM("{amount_col}") AS monthly_total
            FROM data
            WHERE "{amount_col}" IS NOT NULL{type_filter}
            GROUP BY "{category_col}", month
        ) sub
        GROUP BY "{category_col}"
        ORDER BY stddev_monthly / NULLIF(AVG(monthly_total), 0)
    """
    rows = run_query(ds, sql).rows
    fixed    = []
    variable = []
    for r in rows:
        cat  = str(r["category"])
        avg  = float(r["avg_monthly"] or 0)
        std  = float(r["stddev_monthly"] or 0)
        cv   = std / avg if avg > 0 else 0.0
        if cv <= cv_threshold:
            fixed.append((cat, avg, cv))
        else:
            variable.append((cat, avg, cv))
    render_fixed_variable(fixed, variable)
