"""Personal-finance commands.

Every command here reads the same shape of file - a row per transaction, with
an amount, a date, and usually a column saying whether the row is income or
expense - so they all take the same handful of column-name options and all
open by working out the same things about the file. `Money` resolves that once
and carries the SQL fragments that depend on it.
"""

import re
from calendar import monthrange
from dataclasses import dataclass
from datetime import date as date_type
from pathlib import Path
from typing import Annotated

import typer

from dv.app import (
    app,
    limit_or_default,
)
from dv.app import (
    ds as _ds,
)
from dv.core.datasource import DataSource
from dv.core.errors import DvError
from dv.core.query import require_columns, run_query
from dv.core.schema import get_schema
from dv.core.sql import ident, lit, order_by_agg, order_by_row, period_expr
from dv.render.common import fmt_date
from dv.render.money import (
    render_budget,
    render_burn_rate,
    render_drill,
    render_expenses_by,
    render_fixed_variable,
    render_forecast,
    render_income_expense,
    render_money_report,
    render_money_summary,
    render_note_analysis,
    render_remaining,
    render_savings_rate,
    render_spend_by_weekday,
    render_subscriptions,
)
from dv.render.table import render_table
from dv.render.theme import console

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# ── Shared options ────────────────────────────────────────────────────────────
# The same five column names are asked for by most of the commands below.
# Declared once so the help text cannot drift between them.

TypeCol    = Annotated[str, typer.Option("--type",    help="Transaction type column")]
AmountCol  = Annotated[str, typer.Option("--amount",  help="Amount column")]
DateCol    = Annotated[str, typer.Option("--date",    help="Date column")]
IncomeVal  = Annotated[str, typer.Option("--income",  help="Value meaning income")]
ExpenseVal = Annotated[str, typer.Option("--expense", help="Value meaning expense")]
CategoryCol = Annotated[str, typer.Option("--category-col", help="Category column")]
LimitOpt   = Annotated[int | None, typer.Option("--limit", "-l")]
ByOpt      = Annotated[str, typer.Option("--by", help="day|week|month|year")]


# ── Shared context ────────────────────────────────────────────────────────────

@dataclass
class Money:
    """The columns, values and derived SQL the money commands share.

    Thirteen commands used to open with the same four lines - take the source,
    fetch the schema, ask whether the file has a type column, build the expense
    filter from the answer. `Money.load()` does that once and hands back the
    fragments already bound to the column names.
    """

    ds: DataSource
    amount: str
    type_col: str
    expense_val: str
    income_val: str = "income"
    date: str | None = None
    columns: frozenset[str] = frozenset()

    @property
    def has_type(self) -> bool:
        """Whether the file separates income from expense at all."""
        return self.type_col in self.columns

    @classmethod
    def load(
        cls,
        amount: str,
        type_col: str,
        expense_val: str,
        income_val: str = "income",
        date: str | None = None,
        *,
        needs: str | tuple[str, ...] = (),
    ) -> "Money":
        """Resolve the shared context, checking `amount`, `date` and `needs` exist."""
        extra = (needs,) if isinstance(needs, str) else tuple(needs)
        ds = _ds()
        require_columns(ds, amount, date, *extra)
        # get_schema walks the whole table to count nulls and distinct values,
        # so it is taken once here and the names kept - `has` is asked several
        # times per command and must not pay for a scan each time.
        return cls(
            ds=ds, amount=amount, type_col=type_col, expense_val=expense_val,
            income_val=income_val, date=date,
            columns=frozenset(c.name for c in get_schema(ds).columns),
        )

    def has(self, column: str) -> bool:
        """Whether the file carries an optional column, like `subcategory`."""
        return column in self.columns

    # -- SQL fragments --------------------------------------------------------

    @property
    def expense_where(self) -> str:
        """A WHERE clause selecting the expense rows.

        A file with a type column marks income and expense separately; one
        without is all spending, so the clause only has to skip rows with no
        amount.
        """
        if self.has_type:
            return f"WHERE {ident(self.type_col)} = {lit(self.expense_val)}"
        return f"WHERE {ident(self.amount)} IS NOT NULL"

    @property
    def expense_and(self) -> str:
        """The same restriction as a fragment, to append to an existing WHERE."""
        if self.has_type:
            return f" AND {ident(self.type_col)} = {lit(self.expense_val)}"
        return ""

    def typed_sum(self, value: str) -> str:
        """Total the amount column over rows of one transaction type."""
        return (f"sum(CASE WHEN {ident(self.type_col)} = {lit(value)} "
                f"THEN {ident(self.amount)} ELSE 0 END)")

    # -- Shared queries -------------------------------------------------------

    def query(self, sql: str) -> list[dict]:
        return run_query(self.ds, sql).rows

    def expense_totals(self, column: str, limit: int | None = None) -> list[tuple[str, float]]:
        """Expenses grouped by a column, largest first."""
        cap = f" LIMIT {int(limit)}" if limit is not None else ""
        rows = self.query(
            f"SELECT {ident(column)}, sum({ident(self.amount)}) AS total "
            f"FROM data {self.expense_where} GROUP BY {ident(column)} "
            f"{order_by_agg('total', column)}{cap}"
        )
        return [(str(r[column]), float(r["total"])) for r in rows]

    def by_period(self, by: str, newest_first: bool = False,
                  limit: int | None = None) -> list[dict]:
        """Income and expense totalled per time bucket.

        income-expense, savings-rate and forecast all want exactly this; they
        differ only in which end of it they read and how they draw it.
        """
        p = period_expr(self.date, by)
        order = f"{p} DESC" if newest_first else p
        cap = f" LIMIT {int(limit)}" if limit is not None else ""
        income = self.typed_sum(self.income_val) if self.has_type else "0"
        expense = (self.typed_sum(self.expense_val) if self.has_type
                   else f"sum({ident(self.amount)})")
        rows = self.query(
            f"SELECT {p} AS period, {income} AS income, {expense} AS expense "
            f"FROM data WHERE {ident(self.date)} IS NOT NULL "
            f"GROUP BY {p} ORDER BY {order}{cap}"
        )
        return [{"period": str(r["period"]),
                 "income": float(r["income"] or 0),
                 "expense": float(r["expense"] or 0)} for r in rows]

    def month_spend(self, month: str) -> float:
        """Total expenses within one YYYY-MM month."""
        rows = self.query(
            f"SELECT COALESCE(sum({ident(self.amount)}), 0) AS spent FROM data "
            f"WHERE strftime({ident(self.date)}::DATE, '%Y-%m') = {lit(month)}"
            f"{self.expense_and}"
        )
        return float(rows[0]["spent"])

    def latest_month(self) -> str:
        """The YYYY-MM of the newest row, for commands that default to it."""
        rows = self.query(f"SELECT max({ident(self.date)}) AS mx FROM data")
        return str(rows[0]["mx"])[:7]

    def date_range(self) -> tuple[str, str] | None:
        rows = self.query(f"SELECT min({ident(self.date)}) AS mn, "
                          f"max({ident(self.date)}) AS mx FROM data")
        mn, mx = rows[0]["mn"], rows[0]["mx"]
        return (fmt_date(mn), fmt_date(mx)) if mn else None


def _parse_month(month: str) -> tuple[int, int]:
    """Parse a YYYY-MM option value."""
    m = re.fullmatch(r"(\d{4})-(\d{2})", str(month).strip())
    if not m:
        raise DvError(f"Invalid --month: {month!r}", hint="Expected YYYY-MM, e.g. 2026-06")
    year, mon = int(m.group(1)), int(m.group(2))
    if not 1 <= mon <= 12:
        raise DvError(f"Invalid month number in {month!r}", hint="Month must be 01-12")
    return year, mon


def _month_progress(month: str) -> tuple[int, int]:
    """How far through `month` we are: (days elapsed, days in the month).

    Part-way through the current month the pace so far is what matters; for a
    past month the whole month has elapsed.
    """
    year, mon = _parse_month(month)
    days_total = monthrange(year, mon)[1]
    today = date_type.today()
    days_passed = today.day if (today.year, today.month) == (year, mon) else days_total
    return days_passed, days_total


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
        raise DvError(f"Could not parse {path}", hint=str(e).splitlines()[0]) from e
    if not isinstance(data, dict):
        raise DvError(f"{path} must be a mapping of category to amount")
    out = {}
    for key, value in data.items():
        try:
            out[str(key)] = float(value)
        except (TypeError, ValueError) as e:
            raise DvError(f"Budget for {key!r} is not a number: {value!r}") from e
    return out


@app.command(name="money-summary")
def money_summary(
    type_col: TypeCol = "type",
    amount_col: AmountCol = "amount",
    date_col: DateCol = "date",
    income_val: IncomeVal = "income",
    expense_val: ExpenseVal = "expense",
):
    """Show money summary: income, expenses, savings rate."""
    m = Money.load(amount_col, type_col, expense_val, income_val, date_col)

    stats = m.query(
        f"SELECT COALESCE(sum({ident(m.amount)}), 0) AS total, "
        f"       count(*)                            AS cnt, "
        f"       COALESCE(avg({ident(m.amount)}), 0) AS avg_val, "
        f"       COALESCE(max({ident(m.amount)}), 0) AS max_val "
        f"FROM data {m.expense_where}"
    )[0]
    income = 0.0
    if m.has_type:
        income = float(m.query(
            f"SELECT COALESCE(sum({ident(m.amount)}), 0) AS total FROM data "
            f"WHERE {ident(m.type_col)} = {lit(income_val)}"
        )[0]["total"])

    accounts: list[str] = []
    if m.has("account"):
        accounts = [str(r["account"]) for r in m.query(
            "SELECT DISTINCT account FROM data WHERE account IS NOT NULL ORDER BY account")]

    render_money_summary(
        income, float(stats["total"]), int(stats["cnt"]),
        float(stats["avg_val"]), float(stats["max_val"]),
        m.date_range(), accounts or None,
    )


@app.command(name="expenses-by")
def expenses_by(
    column: Annotated[str, typer.Argument(help="Column to group by")],
    type_col: TypeCol = "type",
    amount_col: AmountCol = "amount",
    expense_val: ExpenseVal = "expense",
    limit: LimitOpt = None,
):
    """Show expenses broken down by a column (bar chart with %)."""
    m = Money.load(amount_col, type_col, expense_val, needs=column)
    items = m.expense_totals(column, limit_or_default(limit, 15))
    render_expenses_by(items, title=f"EXPENSES BY {column.upper()}")


@app.command(name="income-expense")
def income_expense_cmd(
    by: ByOpt = "month",
    type_col: TypeCol = "type",
    amount_col: AmountCol = "amount",
    date_col: DateCol = "date",
    income_val: IncomeVal = "income",
    expense_val: ExpenseVal = "expense",
):
    """Show income vs expense by time period."""
    m = Money.load(amount_col, type_col, expense_val, income_val, date_col)
    render_income_expense(m.by_period(by))


@app.command(name="savings-rate")
def savings_rate_cmd(
    by: ByOpt = "month",
    type_col: TypeCol = "type",
    amount_col: AmountCol = "amount",
    date_col: DateCol = "date",
    income_val: IncomeVal = "income",
    expense_val: ExpenseVal = "expense",
):
    """Show savings rate trend by time period."""
    m = Money.load(amount_col, type_col, expense_val, income_val, date_col)
    render_savings_rate(m.by_period(by))


@app.command()
def largest(
    amount_col: AmountCol = "amount",
    type_col: TypeCol = "type",
    expense_val: ExpenseVal = "expense",
    limit: Annotated[int | None, typer.Option("--limit", "-l", "--n")] = None,
):
    """Show the largest transactions sorted by amount."""
    m = Money.load(amount_col, type_col, expense_val)
    result = run_query(m.ds, f"SELECT * FROM data {m.expense_where} "
                             f"{order_by_row(amount_col)} LIMIT {limit_or_default(limit, 10)}")
    render_table(result, title="LARGEST TRANSACTIONS")


@app.command()
def budget(
    column: Annotated[str, typer.Argument(help="Category column")],
    budget_file: Annotated[Path, typer.Option("--budget",
                                              help="YAML file with category budgets")],
    type_col: TypeCol = "type",
    amount_col: AmountCol = "amount",
    expense_val: ExpenseVal = "expense",
):
    """Compare actual spending against a YAML budget file."""
    m = Money.load(amount_col, type_col, expense_val, needs=column)
    render_budget(m.expense_totals(column), _load_budget(budget_file))


@app.command(name="burn-rate")
def burn_rate(
    budget_amount: Annotated[float, typer.Option("--budget", help="Monthly budget")],
    month: Annotated[str, typer.Option("--month", help="Month as YYYY-MM (default: latest)")] = "",
    type_col: TypeCol = "type",
    amount_col: AmountCol = "amount",
    date_col: DateCol = "date",
    expense_val: ExpenseVal = "expense",
):
    """Show spending pace vs budget for a month."""
    m = Money.load(amount_col, type_col, expense_val, date=date_col)
    month = month or m.latest_month()
    days_passed, days_total = _month_progress(month)
    year, mon = _parse_month(month)
    render_burn_rate(m.month_spend(month), budget_amount, days_passed, days_total,
                     f"{MONTH_ABBR[mon - 1]} {year}")


@app.command()
def remaining(
    budget: Annotated[float, typer.Option("--budget", help="Total budget for the month")],
    month: Annotated[str, typer.Option("--month", help="Month YYYY-MM (default: current)")] = "",
    date_col: DateCol = "date",
    amount_col: AmountCol = "amount",
    type_col: TypeCol = "type",
    expense_val: ExpenseVal = "expense",
):
    """Budget remaining and safe daily spend."""
    m = Money.load(amount_col, type_col, expense_val, date=date_col)
    month = month or date_type.today().strftime("%Y-%m")
    days_passed, days_total = _month_progress(month)
    render_remaining(m.month_spend(month), budget, days_passed, days_total, month_label=month)


@app.command()
def subscriptions(
    type_col: TypeCol = "type",
    amount_col: AmountCol = "amount",
    date_col: DateCol = "date",
    note_col: Annotated[str, typer.Option("--note",
                                          help="Column to group recurring by")] = "note",
    expense_val: ExpenseVal = "expense",
    min_months: Annotated[int, typer.Option(
        "--min-months", help="Minimum months to count as recurring")] = 2,
):
    """Detect recurring payments (same name, similar amount, multiple months)."""
    m = Money.load(amount_col, type_col, expense_val, date=date_col, needs=note_col)
    rows = m.query(f"""
        WITH monthly AS (
            SELECT {ident(note_col)} AS name,
                   strftime({ident(date_col)}::DATE, '%Y-%m') AS month,
                   avg({ident(amount_col)}) AS avg_amount
            FROM data
            WHERE {ident(note_col)} IS NOT NULL{m.expense_and}
            GROUP BY {ident(note_col)}, strftime({ident(date_col)}::DATE, '%Y-%m')
        )
        SELECT name, count(DISTINCT month) AS months, avg(avg_amount) AS amount
        FROM monthly
        GROUP BY name
        HAVING count(DISTINCT month) >= {int(min_months)}
        ORDER BY months DESC, amount DESC, name
    """)
    render_subscriptions([{"name": r["name"], "amount": r["amount"], "months": r["months"]}
                          for r in rows])


@app.command(name="money-report")
def money_report(
    month: Annotated[str, typer.Option("--month", help="Month YYYY-MM (default: all)")] = "",
    type_col: TypeCol = "type",
    amount_col: AmountCol = "amount",
    date_col: DateCol = "date",
    category_col: CategoryCol = "category",
    income_val: IncomeVal = "income",
    expense_val: ExpenseVal = "expense",
    budget_file: Annotated[Path | None, typer.Option("--budget")] = None,
):
    """Full money report: summary, expenses by category, cashflow."""
    m = Money.load(amount_col, type_col, expense_val, income_val, date_col, needs=category_col)

    in_month = f"strftime({ident(date_col)}::DATE, '%Y-%m') = {lit(month)}"
    and_month = f" AND {in_month}" if month else ""
    # The category and largest-transaction queries need a WHERE to hang the
    # type filter off, so they start from 1=1 when no month was given.
    expense_filter = (f" WHERE {in_month}" if month else " WHERE 1=1") + m.expense_and
    if not m.has_type:
        expense_filter += f" AND {ident(amount_col)} IS NOT NULL"

    def total(where: str) -> float:
        return float(m.query(f"SELECT COALESCE(sum({ident(amount_col)}), 0) AS total "
                             f"FROM data WHERE {where}")[0]["total"])

    if m.has_type:
        income = total(f"{ident(type_col)} = {lit(income_val)}{and_month}")
        expense = total(f"{ident(type_col)} = {lit(expense_val)}{and_month}")
    else:
        income = 0.0
        expense = total(f"{ident(amount_col)} IS NOT NULL{and_month}")

    cats = m.query(f"SELECT {ident(category_col)}, sum({ident(amount_col)}) AS total "
                   f"FROM data{expense_filter} GROUP BY {ident(category_col)} "
                   f"{order_by_agg('total', category_col)} LIMIT 15")
    largest_rows = m.query(f"SELECT {ident(date_col)}, {ident(category_col)}, "
                           f"{ident(amount_col)} FROM data{expense_filter} "
                           f"{order_by_row(amount_col)} LIMIT 5")

    render_money_report(
        income, expense,
        [(str(r[category_col]), float(r["total"])) for r in cats],
        m.date_range(), largest_rows,
        _load_budget(budget_file) if budget_file else None,
        month_label=month,
    )


@app.command()
def drill(
    category: Annotated[str | None, typer.Argument(help="Category value to drill into")] = None,
    category_opt: Annotated[str | None, typer.Option(
        "--category", help="Category value (same as the argument)")] = None,
    category_col: CategoryCol = "category",
    subcat_col: Annotated[str, typer.Option("--subcat")] = "subcategory",
    amount_col: AmountCol = "amount",
    date_col: DateCol = "date",
    type_col: TypeCol = "type",
    expense_val: ExpenseVal = "expense",
    n: Annotated[int, typer.Option("--n", "--limit", "-l",
                                   help="Top N largest transactions")] = 5,
):
    """Drill into a single category: subcategory breakdown + largest transactions."""
    # `dv money.csv drill --category food` reads as naturally as the positional
    # form, so accept both rather than failing on a plausible invocation.
    category = category_opt if category_opt is not None else category
    if category is None:
        raise DvError("No category given", hint="Usage: dv <file> drill <category>")

    m = Money.load(amount_col, type_col, expense_val, date=date_col, needs=category_col)
    where = f"WHERE {ident(category_col)} = {lit(category)}{m.expense_and}"

    stats = m.query(f"SELECT COUNT(*) AS cnt, SUM({ident(amount_col)}) AS total, "
                    f"AVG({ident(amount_col)}) AS avg FROM data {where}")
    row = stats[0] if stats else {}

    subcats: list[tuple[str, float]] = []
    has_subcat = m.has(subcat_col)
    if has_subcat:
        subcats = [(str(r[subcat_col]), float(r["t"])) for r in m.query(
            f"SELECT {ident(subcat_col)}, SUM({ident(amount_col)}) AS t FROM data {where} "
            f"GROUP BY {ident(subcat_col)} {order_by_agg('t', subcat_col)}")]

    detail = subcat_col if has_subcat else category_col
    largest_rows = m.query(f"SELECT {ident(date_col)}, {ident(detail)}, {ident(amount_col)} "
                           f"FROM data {where} {order_by_row(amount_col)} LIMIT {int(n)}")
    render_drill(category, float(row.get("total") or 0), int(row.get("cnt") or 0),
                 float(row.get("avg") or 0), subcats, largest_rows)


@app.command(name="spend-by-weekday")
def spend_by_weekday(
    date_col: DateCol = "date",
    amount_col: AmountCol = "amount",
    type_col: TypeCol = "type",
    expense_val: ExpenseVal = "expense",
    mode: Annotated[str, typer.Option("--mode", help="total or avg")] = "total",
):
    """Average or total spending by day of week (Mon–Sun)."""
    m = Money.load(amount_col, type_col, expense_val, date=date_col)
    agg = f"SUM({ident(amount_col)})" if mode == "total" else f"AVG({ident(amount_col)})"
    rows = m.query(f"""
        SELECT dayname({ident(date_col)}::DATE)    AS weekday,
               dayofweek({ident(date_col)}::DATE)  AS dow,
               {agg}                               AS val
        FROM data
        WHERE {ident(amount_col)} IS NOT NULL{m.expense_and}
        GROUP BY weekday, dow
        ORDER BY dow
    """)
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    by_day = {r["weekday"]: float(r["val"] or 0) for r in rows}
    items = [(d[:3], by_day[d]) for d in day_order if d in by_day]
    render_spend_by_weekday(items, title=f"SPENDING BY WEEKDAY ({mode})")


@app.command(name="note-analysis")
def note_analysis(
    note_col: Annotated[str, typer.Option("--note", help="Merchant/note column")] = "note",
    amount_col: AmountCol = "amount",
    type_col: TypeCol = "type",
    expense_val: ExpenseVal = "expense",
    n: Annotated[int, typer.Option("--n", "--limit", "-l", help="Top N merchants")] = 20,
):
    """Group by merchant/note column: count, total, average."""
    m = Money.load(amount_col, type_col, expense_val, needs=note_col)
    rows = m.query(f"""
        SELECT {ident(note_col)}       AS merchant,
               COUNT(*)                AS count,
               SUM({ident(amount_col)}) AS total,
               AVG({ident(amount_col)}) AS avg
        FROM data
        WHERE {ident(amount_col)} IS NOT NULL{m.expense_and}
        GROUP BY {ident(note_col)}
        {order_by_agg("total", note_col)}
        LIMIT {int(n)}
    """)
    render_note_analysis([{"merchant": r["merchant"], "count": r["count"],
                           "total": float(r["total"] or 0), "avg": float(r["avg"] or 0)}
                          for r in rows])


@app.command()
def forecast(
    months_back: Annotated[int, typer.Option("--history",
                                             help="Months of history to average")] = 3,
    months_fwd: Annotated[int, typer.Option("--forward",
                                            help="Months to project forward")] = 3,
    date_col: DateCol = "date",
    amount_col: AmountCol = "amount",
    type_col: TypeCol = "type",
    income_val: IncomeVal = "income",
    expense_val: ExpenseVal = "expense",
):
    """Project future cashflow based on rolling average of recent months."""
    m = Money.load(amount_col, type_col, expense_val, income_val, date_col)
    historical = m.by_period("month", newest_first=True, limit=months_back)
    if not historical:
        console.print("[dim]No data[/dim]")
        return

    avg_inc = sum(r["income"] for r in historical) / len(historical)
    avg_exp = sum(r["expense"] for r in historical) / len(historical)

    today = date_type.today()
    year, mon = today.year, today.month
    projected = []
    for _ in range(months_fwd):
        mon += 1
        if mon > 12:
            mon, year = 1, year + 1
        projected.append({"period": f"{year}-{mon:02d}",
                          "income": avg_inc, "expense": avg_exp})

    render_forecast(historical[::-1], projected)


@app.command(name="fixed-variable")
def fixed_variable(
    date_col: DateCol = "date",
    amount_col: AmountCol = "amount",
    category_col: CategoryCol = "category",
    type_col: TypeCol = "type",
    expense_val: ExpenseVal = "expense",
    cv_threshold: Annotated[float, typer.Option(
        "--threshold", help="Coefficient of variation threshold for 'fixed'")] = 0.15,
):
    """Classify expense categories as fixed (low variance) vs variable (high variance)."""
    m = Money.load(amount_col, type_col, expense_val, date=date_col, needs=category_col)
    rows = m.query(f"""
        SELECT {ident(category_col)}  AS category,
               AVG(monthly_total)     AS avg_monthly,
               STDDEV(monthly_total)  AS stddev_monthly
        FROM (
            SELECT {ident(category_col)},
                   strftime({ident(date_col)}::DATE, '%Y-%m') AS month,
                   SUM({ident(amount_col)}) AS monthly_total
            FROM data
            WHERE {ident(amount_col)} IS NOT NULL{m.expense_and}
            GROUP BY {ident(category_col)}, month
        ) sub
        GROUP BY {ident(category_col)}
        ORDER BY stddev_monthly / NULLIF(AVG(monthly_total), 0), {ident(category_col)}
    """)
    fixed, variable = [], []
    for r in rows:
        avg = float(r["avg_monthly"] or 0)
        std = float(r["stddev_monthly"] or 0)
        cv = std / avg if avg > 0 else 0.0
        (fixed if cv <= cv_threshold else variable).append((str(r["category"]), avg, cv))
    render_fixed_variable(fixed, variable)
