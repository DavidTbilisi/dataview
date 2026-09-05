from rich.text import Text

from dv.render.common import (
    bar,
    bar_rows,
    gauge,
    kv_pairs,
    section,
    simple_table,
    subsection,
    threshold_style,
)
from dv.render.json_out import emit, json_mode
from dv.render.theme import charset, console


def render_money_summary(
    income: float,
    expense: float,
    tx_count: int,
    avg_expense: float,
    max_expense: float,
    date_range: tuple[str, str] | None = None,
    accounts: list[str] | None = None,
) -> None:
    if json_mode():
        emit("money", {
            "income": income,
            "expense": expense,
            "saved": income - expense,
            "savings_rate": (income - expense) / income * 100 if income > 0 else 0.0,
            "transactions": tx_count,
            "avg_expense": avg_expense,
            "max_expense": max_expense,
            "date_range": list(date_range) if date_range else None,
            "accounts": accounts or [],
        })
        return

    saved        = income - expense
    savings_rate = saved / income * 100 if income > 0 else 0.0
    cashflow_style = "green" if saved > 0 else ("dim" if saved == 0 else "red")
    cashflow_status = "POSITIVE" if saved > 0 else ("NEUTRAL" if saved == 0 else "NEGATIVE")

    section("MONEY SUMMARY")

    if date_range:
        console.print(f"  [dim]period[/dim]        "
                      f"{date_range[0]} {charset().arrow} {date_range[1]}")
        console.print()

    pairs = [
        ("income",       f"{income:,.2f}"),
        ("expenses",     f"{expense:,.2f}"),
        ("saved",        f"{saved:,.2f}"),
        ("savings rate", f"{savings_rate:.1f}%"),
    ]
    kv_pairs(pairs)

    console.print()
    pairs2 = [
        ("transactions", f"{tx_count:,}"),
        ("avg expense",  f"{avg_expense:,.2f}"),
        ("max expense",  f"{max_expense:,.2f}"),
    ]
    if accounts:
        pairs2.append(("accounts", ", ".join(accounts)))
    kv_pairs(pairs2)

    console.print()
    console.print(f"  [dim]cashflow:[/dim]  [{cashflow_style}]{cashflow_status}[/{cashflow_style}]")
    console.print()


def render_expenses_by(
    items: list[tuple[str, float]],
    title: str = "EXPENSES BY CATEGORY",
) -> None:
    if json_mode():
        emit("items", [{"label": k, "value": v} for k, v in items])
        return

    if not items:
        console.print("[dim]No data[/dim]")
        return

    total = sum(v for _, v in items) or 1

    section(title)
    bar_rows(items)

    console.print()
    console.print(Text(f"  Total: {total:,.2f}", style="bold"))
    console.print()


def render_income_expense(
    rows: list[dict],
    title: str = "INCOME VS EXPENSE",
) -> None:
    """Income against expense per period, with the savings rate and its trend.

    rows: [{"period": ..., "income": ..., "expense": ...}]
    """
    if json_mode():
        emit("rows", rows)
        return

    if not rows:
        console.print("[dim]No data[/dim]")
        return

    section(title)

    t = simple_table()
    t.add_column("period",  style="bold")
    t.add_column("income",  justify="right", style="green")
    t.add_column("expense", justify="right", style="red")
    t.add_column("saved",   justify="right")
    t.add_column("rate",    justify="right")

    total_income = total_expense = 0.0
    rates: list[float] = []
    for r in rows:
        inc  = float(r.get("income") or 0)
        exp  = float(r.get("expense") or 0)
        saved = inc - exp
        rate  = saved / inc * 100 if inc > 0 else 0.0
        rates.append(rate)
        total_income  += inc
        total_expense += exp
        t.add_row(
            str(r["period"]),
            f"{inc:,.2f}",
            f"{exp:,.2f}",
            Text(f"{saved:,.2f}", style="green" if saved >= 0 else "red"),
            Text(f"{rate:.1f}%",
                 style="green" if rate >= 20 else ("yellow" if rate >= 0 else "red")),
        )

    total_saved = total_income - total_expense
    total_rate  = total_saved / total_income * 100 if total_income else 0.0
    t.add_row(
        "TOTAL",
        Text(f"{total_income:,.2f}",  style="bold green"),
        Text(f"{total_expense:,.2f}", style="bold red"),
        Text(f"{total_saved:,.2f}",   style="bold"),
        Text(f"{total_rate:.1f}%",    style="bold cyan"),
    )
    console.print(t)

    if rates:
        avg_rate = sum(rates) / len(rates)
        low, high = min(rates), max(rates)
        span = high - low or 1
        glyphs = charset().spark
        trend = "".join(glyphs[min(len(glyphs) - 1,
                                   int((r - low) / span * (len(glyphs) - 1)))]
                        for r in rates)
        console.print()
        console.print(f"  [dim]avg rate:[/dim]  [cyan]{avg_rate:.1f}%[/cyan]  "
                      f"[dim]trend: {trend}[/dim]")
    console.print()


def render_budget(
    items: list[tuple[str, float]],
    budget_dict: dict[str, float],
    title: str = "BUDGET VS ACTUAL",
) -> None:
    """items: [(category, actual_amount)]"""
    if json_mode():
        emit("budget", [
            {"category": k, "actual": v, "budget": budget_dict.get(k),
             "remaining": (budget_dict.get(k) - v)
                          if budget_dict.get(k) is not None else None}
            for k, v in items
        ])
        return

    if not items and not budget_dict:
        console.print("[dim]No data[/dim]")
        return

    actual_map = dict(items)
    # All categories: budgeted ones first, then unbudgeted actuals
    all_cats = list(dict.fromkeys(
        list(budget_dict.keys()) + [c for c, _ in items if c not in budget_dict]
    ))

    bar_w = 20

    section(title)

    t = simple_table()
    t.add_column("category", style="bold")
    t.add_column("budget",   justify="right")
    t.add_column("actual",   justify="right")
    t.add_column("diff",     justify="right")
    t.add_column("status")
    t.add_column("usage", min_width=bar_w)

    for cat in all_cats:
        budget = budget_dict.get(cat, 0.0)
        actual = actual_map.get(cat, 0.0)
        diff   = actual - budget

        if budget == 0:
            status   = Text(f"{charset().emdash}", style="dim")
            bar_text = Text(charset().empty * bar_w, style="dim")
        else:
            pct = actual / budget
            bar = gauge(pct, bar_w)
            if pct > 1.0:
                status   = Text("OVER", style="bold red")
                bar_text = Text(f"{bar:<{bar_w}}", style="red")
            elif pct > 0.9:
                status   = Text("WARN", style="yellow")
                bar_text = Text(f"{bar:<{bar_w}}", style="yellow")
            else:
                status   = Text("OK", style="green")
                bar_text = Text(f"{bar:<{bar_w}}", style="green")

        diff_text = Text(
            f"+{diff:,.2f}" if diff > 0 else f"{diff:,.2f}",
            style="red" if diff > 0 else "green",
        )
        t.add_row(cat, f"{budget:,.2f}", f"{actual:,.2f}", diff_text, status, bar_text)

    console.print(t)
    console.print()


def render_burn_rate(
    spent: float,
    budget: float,
    days_passed: int,
    days_total: int,
    month_label: str = "",
) -> None:
    remaining    = budget - spent
    days_left    = days_total - days_passed
    daily_budget = budget / days_total if days_total else 0.0
    daily_actual = spent / days_passed if days_passed else 0.0
    safe_daily   = remaining / days_left if days_left > 0 else 0.0
    projected    = daily_actual * days_total
    pace         = daily_actual / daily_budget if daily_budget else 0.0

    if json_mode():
        emit("burn_rate", {
            "month": month_label or None, "spent": spent, "budget": budget,
            "remaining": remaining, "days_passed": days_passed,
            "days_left": days_left, "days_total": days_total,
            "daily_budget": daily_budget, "daily_actual": daily_actual,
            "safe_daily": safe_daily, "projected": projected, "pace": pace,
            "pct_spent": (spent / budget * 100) if budget else 0.0,
        })
        return

    title = f"BURN RATE{': ' + month_label if month_label else ''}"
    section(title)

    kv_pairs([
        ("budget",        f"{budget:,.2f}"),
        ("spent",         f"{spent:,.2f}  (day {days_passed} of {days_total})"),
        ("remaining",     f"{remaining:,.2f}"),
        ("days left",     f"{days_left}"),
        ("daily budget",  f"{daily_budget:,.2f}"),
        ("daily actual",  f"{daily_actual:,.2f}"),
        ("projected",     f"{projected:,.2f}"),
    ])

    console.print()
    status = "ON TRACK" if pace <= 1.0 else "OVER PACE"
    style  = "green" if pace <= 1.0 else "red"
    console.print(f"  Status: [{style}]{status}[/{style}]  "
                  f"({pace:.1f}{charset().times} daily rate)")
    # What is left to spend per remaining day, which is the number you act on.
    safe_style = threshold_style(safe_daily, daily_budget, 0.0)
    console.print(f"  [dim]safe daily spend:[/dim]  "
                  f"[{safe_style}]{safe_daily:,.2f}[/{safe_style}]  "
                  f"[dim]over {days_left} remaining day{'' if days_left == 1 else 's'}[/dim]")
    console.print()

    bar_w = 30

    def _pbar(label: str, pct: float, vstr: str) -> None:
        bar = gauge(pct, bar_w)
        bstyle   = "red" if pct > 1.0 else ("yellow" if pct > 0.85 else "green")
        line     = Text(f"  {label:<12}  [")
        line.append(bar, style=bstyle)
        line.append(f"]  {vstr}")
        console.print(line)

    time_pct  = days_passed / days_total if days_total else 0
    spend_pct = spent / budget if budget else 0
    proj_pct  = projected / budget if budget else 0

    _pbar("time",      time_pct,  f"{time_pct*100:.0f}% of month")
    _pbar("spent",     spend_pct, f"{spend_pct*100:.0f}% of budget")
    _pbar("projected", proj_pct,  f"{projected:,.2f}")
    console.print()


def render_subscriptions(
    items: list[dict],
    title: str = "SUBSCRIPTIONS",
) -> None:
    """items: [{"name": ..., "amount": ..., "months": ..., "count": ...}]"""
    if json_mode():
        emit("subscriptions", items)
        return

    if not items:
        console.print("[dim]No recurring payments detected[/dim]")
        return

    section(title)

    t = simple_table()
    t.add_column("name",       style="bold")
    t.add_column("avg amount", justify="right")
    t.add_column("months",     justify="right", style="dim")
    t.add_column("est yearly", justify="right", style="cyan")

    monthly_total = 0.0
    for item in items:
        name     = str(item.get("name", ""))
        amount   = float(item.get("amount") or 0)
        months   = int(item.get("months") or 1)
        yearly   = amount * 12
        monthly_total += amount
        t.add_row(name, f"{amount:,.2f}", str(months), f"{yearly:,.2f}")

    console.print(t)
    console.print()
    console.print(f"  [dim]monthly total:[/dim]  {monthly_total:,.2f}")
    console.print(f"  [dim]yearly total: [/dim]  {monthly_total * 12:,.2f}")
    console.print()


def render_money_report(
    income: float,
    expense: float,
    expense_by_cat: list[tuple[str, float]],
    date_range: tuple[str, str] | None,
    largest: list[dict],
    budget_dict: dict[str, float] | None = None,
    month_label: str = "",
) -> None:
    if json_mode():
        emit("money_report", {
            "income": income,
            "expense": expense,
            "saved": income - expense,
            "date_range": list(date_range) if date_range else None,
            "by_category": [{"label": k, "value": v} for k, v in expense_by_cat],
            "largest": largest,
            "budget": budget_dict or {},
            "month": month_label or None,
        })
        return

    title = f"MONEY REPORT{': ' + month_label if month_label else ''}"
    section(title)

    saved        = income - expense
    savings_rate = saved / income * 100 if income > 0 else 0.0

    if date_range:
        console.print(f"  [dim]period[/dim]  {date_range[0]} {charset().arrow} {date_range[1]}")
        console.print()

    # Summary
    subsection("SUMMARY")
    pairs = [
        ("income",       f"{income:,.2f}"),
        ("expenses",     f"{expense:,.2f}"),
        ("saved",        f"{saved:,.2f}"),
        ("savings rate", f"{savings_rate:.1f}%"),
    ]
    kv_pairs(pairs)
    console.print()

    # Expenses by category
    if expense_by_cat:
        subsection("EXPENSES BY CATEGORY")
        bar_rows(expense_by_cat[:10])
        console.print()

    # Budget status
    if budget_dict and expense_by_cat:
        actual_map = dict(expense_by_cat)
        over = [(c, b) for c, b in budget_dict.items() if actual_map.get(c, 0) > b]
        ok   = [(c, b) for c, b in budget_dict.items() if actual_map.get(c, 0) <= b]
        if over or ok:
            subsection("BUDGET STATUS")
            for cat, bgt in over:
                diff = actual_map.get(cat, 0) - bgt
                console.print(f"  [red]OVER[/red]  {cat:<20}  +{diff:,.2f}")
            for cat, bgt in ok:
                diff = actual_map.get(cat, 0) - bgt
                console.print(f"  [green]OK  [/green]  {cat:<20}   {diff:,.2f}")
            console.print()

    # Largest transactions
    if largest:
        subsection("LARGEST TRANSACTIONS")
        t = simple_table()
        cols = list(largest[0].keys())
        for c in cols:
            t.add_column(c)
        for r in largest:
            t.add_row(*[str(r.get(c, "")) for c in cols])
        console.print(t)
        console.print()

    # Cashflow bars
    subsection("CASHFLOW")
    max_flow = max(income, expense, abs(saved)) or 1
    bar_w    = 25

    def _fbar(label: str, v: float, style: str) -> None:
        drawn = bar(abs(v), max_flow, bar_w)
        line = Text(f"  {label:<8}  ")
        line.append(f"{drawn:<{bar_w}}", style=style)
        line.append(f"  {v:,.2f}")
        console.print(line)

    _fbar("income",  income,  "green")
    _fbar("expense", expense, "red")
    _fbar("saved",   saved,   "green" if saved >= 0 else "red")
    console.print()


def render_drill(
    category: str,
    total: float,
    tx_count: int,
    avg: float,
    subcats: list[tuple[str, float]],
    largest: list[dict],
    title: str = "",
) -> None:
    """Category drilldown: stats + subcategory bars + largest transactions."""
    if json_mode():
        emit("drill", {
            "category": category,
            "total": total,
            "transactions": tx_count,
            "average": avg,
            "subcategories": [{"label": k, "value": v} for k, v in subcats],
            "largest": largest,
        })
        return

    title = title or f"CATEGORY: {category}"
    section(title)

    console.print(f"  [dim]total       [/dim]  {total:,.2f}")
    console.print(f"  [dim]transactions[/dim]  {tx_count:,}")
    console.print(f"  [dim]average     [/dim]  {avg:,.2f}")
    console.print()

    if subcats:
        subsection("SUBCATEGORIES")
        bar_rows(subcats, show_pct=False)
        console.print()

    if largest:
        subsection("LARGEST TRANSACTIONS")
        t = simple_table()
        for col in largest[0]:
            t.add_column(col)
        for r in largest:
            t.add_row(*[str(r.get(c, "")) for c in largest[0]])
        console.print(t)
        console.print()


def render_spend_by_weekday(
    items: list[tuple[str, float]],
    title: str = "SPENDING BY WEEKDAY",
) -> None:
    """Bar chart of total or average spend per weekday."""
    if json_mode():
        emit("items", [{"weekday": k, "value": v} for k, v in items])
        return

    if not items:
        console.print("[dim]No data[/dim]")
        return

    section(title)
    bar_rows(items, show_pct=False)
    console.print()


def render_note_analysis(
    items: list[dict],
    title: str = "MERCHANT ANALYSIS",
) -> None:
    """Group by note/merchant: count, total, avg."""
    if json_mode():
        emit("rows", items)
        return

    if not items:
        console.print("[dim]No data[/dim]")
        return

    section(title)

    t = simple_table()
    t.add_column("merchant", style="bold")
    t.add_column("count",    justify="right", style="dim")
    t.add_column("total",    justify="right")
    t.add_column("avg",      justify="right", style="cyan")

    grand_total = sum(float(r.get("total") or 0) for r in items)
    for r in items:
        t.add_row(
            str(r.get("merchant", "")),
            str(r.get("count", "")),
            f"{float(r.get('total') or 0):,.2f}",
            f"{float(r.get('avg') or 0):,.2f}",
        )

    console.print(t)
    console.print(Text(f"  Grand total: {grand_total:,.2f}", style="bold"))
    console.print()


def render_forecast(
    historical: list[dict],
    projected: list[dict],
    title: str = "CASHFLOW FORECAST",
) -> None:
    """historical + projected rows, each: {period, income, expense}."""
    if json_mode():
        emit("forecast", {"historical": historical, "projected": projected})
        return

    if not projected:
        console.print("[dim]No data[/dim]")
        return

    section(title)

    if historical:
        avg_inc = sum(float(r.get("income") or 0) for r in historical) / len(historical)
        avg_exp = sum(float(r.get("expense") or 0) for r in historical) / len(historical)
        avg_sav = avg_inc - avg_exp
        n = len(historical)
        console.print(f"  [dim]Based on last {n} month{'s' if n != 1 else ''} average.[/dim]")
        console.print()
        console.print(f"  [dim]expected income: [/dim]  {avg_inc:,.2f}")
        console.print(f"  [dim]expected expense:[/dim]  {avg_exp:,.2f}")
        console.print(f"  [dim]expected saved:  [/dim]  {avg_sav:,.2f}")
        console.print()

    t = simple_table()
    t.add_column("month",   style="bold")
    t.add_column("income",  justify="right", style="green")
    t.add_column("expense", justify="right", style="red")
    t.add_column("saved",   justify="right")

    for r in projected:
        inc  = float(r.get("income") or 0)
        exp  = float(r.get("expense") or 0)
        sav  = inc - exp
        t.add_row(
            str(r["period"]),
            f"{inc:,.2f}",
            f"{exp:,.2f}",
            Text(f"{sav:,.2f}", style="green" if sav >= 0 else "red"),
        )

    console.print(t)
    console.print()


def render_fixed_variable(
    fixed_items: list[tuple[str, float, float]],
    variable_items: list[tuple[str, float, float]],
    title: str = "FIXED VS VARIABLE",
) -> None:
    """fixed/variable_items: [(category, avg_monthly, cv)] where cv = stddev/mean."""
    if json_mode():
        emit("categories", [
            {"category": c, "monthly_avg": a, "variation": v, "kind": kind}
            for kind, group in (("fixed", fixed_items), ("variable", variable_items))
            for c, a, v in group
        ])
        return

    section(title)

    fixed_total    = sum(v for _, v, _ in fixed_items)
    variable_total = sum(v for _, v, _ in variable_items)
    grand_total    = fixed_total + variable_total or 1
    max_v          = grand_total or 1
    bar_w          = 24

    def _section(label: str, items: list[tuple[str, float, float]], total: float, style: str):
        pct = total / grand_total * 100
        drawn = bar(total, max_v, bar_w)
        console.print(f"  [bold]{label}[/bold]  "
                      f"[{style}]{drawn:<{bar_w}}[/{style}]  "
                      f"{total:,.2f}  [dim]{pct:.1f}%[/dim]")
        console.print()
        lw = max((len(c) for c, _, _ in items), default=0)
        vw = max((len(f"{v:,.2f}") for _, v, _ in items), default=0)
        for cat, avg, cv in sorted(items, key=lambda x: -x[1]):
            cv_str = f"cv={cv:.0%}" if cv > 0 else ""
            line   = Text(f"    {cat:<{lw}}  ")
            line.append(f"{avg:>{vw},.2f}", style=style)
            if cv_str:
                line.append(f"  {cv_str}", style="dim")
            console.print(line)
        console.print()

    _section("Fixed expenses",    fixed_items,    fixed_total,    "cyan")
    _section("Variable expenses", variable_items, variable_total, "yellow")
    console.print(Text(f"  Total: {grand_total:,.2f}", style="bold"))
    console.print()
