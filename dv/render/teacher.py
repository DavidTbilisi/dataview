from rich.console import Console
from rich.rule import Rule
from rich.table import Table as RichTable
from rich.text import Text
from rich import box

console = Console()


def _pct(score, max_score) -> float:
    try:
        return float(score) / float(max_score) * 100
    except (TypeError, ZeroDivisionError):
        return 0.0


def _grade_band(pct: float) -> str:
    if pct >= 90: return "A"
    if pct >= 80: return "B"
    if pct >= 70: return "C"
    if pct >= 60: return "D"
    return "F"


def render_teacher_summary(
    rows: list[dict],
    score_col: str = "score",
    max_score_col: str = "max_score",
    student_col: str = "student",
    assignment_col: str = "assignment",
    topic_col: str | None = "topic",
    title: str = "CLASS SUMMARY",
) -> None:
    if not rows:
        console.print("[dim]No data[/dim]")
        return

    pcts = [_pct(r.get(score_col), r.get(max_score_col, 100)) for r in rows
            if r.get(score_col) is not None]
    students    = {r[student_col] for r in rows if r.get(student_col)}
    assignments = {r[assignment_col] for r in rows if r.get(assignment_col)}

    avg    = sum(pcts) / len(pcts) if pcts else 0.0
    sorted_p = sorted(pcts)
    median = sorted_p[len(sorted_p) // 2] if sorted_p else 0.0
    pass_rate = sum(1 for p in pcts if p >= 60) / len(pcts) * 100 if pcts else 0.0

    # Grade bands
    bands = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for p in pcts:
        bands[_grade_band(p)] += 1

    # Per-student avg for at-risk count
    student_avgs: dict[str, list[float]] = {}
    for r in rows:
        s = r.get(student_col)
        p = _pct(r.get(score_col), r.get(max_score_col, 100)) if r.get(score_col) is not None else None
        if s and p is not None:
            student_avgs.setdefault(s, []).append(p)
    at_risk = sum(1 for avgs in student_avgs.values() if (sum(avgs)/len(avgs)) < 70)

    # Weakest topic
    weakest_topic = None
    if topic_col:
        topic_scores: dict[str, list[float]] = {}
        for r in rows:
            tp = r.get(topic_col)
            p  = _pct(r.get(score_col), r.get(max_score_col, 100)) if r.get(score_col) is not None else None
            if tp and p is not None:
                topic_scores.setdefault(tp, []).append(p)
        if topic_scores:
            weakest_topic = min(topic_scores, key=lambda t: sum(topic_scores[t]) / len(topic_scores[t]))

    # Missing submissions: students who have fewer assignments than the max
    max_per_student = max(len(v) for v in student_avgs.values()) if student_avgs else 0
    missing_count = sum(max_per_student - len(v) for v in student_avgs.values())

    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
    console.print()

    pairs = [
        ("students",    str(len(students))),
        ("assignments", str(len(assignments))),
        ("average",     f"{avg:.1f}%"),
        ("median",      f"{median:.1f}%"),
        ("pass rate",   f"{pass_rate:.1f}%"),
    ]
    kw = max(len(k) for k, _ in pairs)
    for k, v in pairs:
        console.print(f"  [dim]{k.ljust(kw)}[/dim]  {v}")

    console.print()
    console.print(Rule("[dim]RISK[/dim]", style="dim", align="left"))
    console.print()
    console.print(f"  [dim]at-risk students:    [/dim]  {at_risk}")
    console.print(f"  [dim]missing submissions: [/dim]  {missing_count}")
    if weakest_topic:
        console.print(f"  [dim]weakest topic:       [/dim]  {weakest_topic}")
    console.print()

    console.print(Rule("[dim]GRADE DISTRIBUTION[/dim]", style="dim", align="left"))
    console.print()
    max_band = max(bands.values()) or 1
    bar_w = 20
    for band, count in bands.items():
        bar   = "#" * max(0, int(count / max_band * bar_w))
        style = "green" if band in ("A", "B") else ("yellow" if band == "C" else "red")
        line  = Text(f"  {band} range  ")
        line.append(f"{bar:<{bar_w}}", style=style)
        line.append(f"  {count}")
        console.print(line)
    console.print()


def render_gradebook(
    rows: list[dict],
    score_col: str = "score",
    max_score_col: str = "max_score",
    student_col: str = "student",
    assignment_col: str = "assignment",
    title: str = "GRADEBOOK",
) -> None:
    if not rows:
        console.print("[dim]No data[/dim]")
        return

    # Build pivot: student → {assignment → pct}
    assignments = sorted({r[assignment_col] for r in rows if r.get(assignment_col)})
    student_data: dict[str, dict[str, float | None]] = {}
    for r in rows:
        s  = r.get(student_col)
        a  = r.get(assignment_col)
        sc = r.get(score_col)
        mx = r.get(max_score_col, 100)
        if not (s and a):
            continue
        student_data.setdefault(s, {})[a] = _pct(sc, mx) if sc is not None else None

    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
    console.print()

    t = RichTable(box=box.SIMPLE_HEAD, header_style="bold dim", show_edge=False, padding=(0, 1))
    t.add_column(student_col, style="bold")
    for a in assignments:
        t.add_column(a, justify="right")
    t.add_column("avg", justify="right", style="cyan")

    for student in sorted(student_data):
        scores = student_data[student]
        cells  = []
        valid  = []
        for a in assignments:
            pct = scores.get(a)
            if pct is None:
                cells.append(Text("--", style="dim"))
            else:
                style = "green" if pct >= 70 else "red"
                cells.append(Text(f"{pct:.0f}%", style=style))
                valid.append(pct)
        avg_str = f"{sum(valid)/len(valid):.1f}%" if valid else "--"
        t.add_row(student, *cells, avg_str)

    console.print(t)
    console.print()
    console.print(Text("  Legend: -- missing submission", style="dim"))
    console.print()


def render_at_risk(
    student_avgs: list[dict],
    title: str = "AT-RISK STUDENTS",
) -> None:
    """student_avgs: [{"student": ..., "avg": ..., "missing": ..., "assignments": ...}]"""
    if not student_avgs:
        console.print("[dim]No at-risk students[/dim]")
        return

    at_risk = []
    ok      = []
    for r in student_avgs:
        avg     = float(r.get("avg") or 0)
        missing = int(r.get("missing") or 0)
        if avg < 60:
            risk = "HIGH"
        elif avg < 70 or missing >= 2:
            risk = "MEDIUM"
        else:
            ok.append(r)
            continue
        reason_parts = []
        if avg < 60:
            reason_parts.append("low score")
        elif avg < 70:
            reason_parts.append("below 70%")
        if missing >= 2:
            reason_parts.append("missing work")
        at_risk.append({**r, "risk": risk, "reason": " + ".join(reason_parts)})

    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
    console.print()

    if not at_risk:
        console.print("  [green]No at-risk students.[/green]")
        console.print()
        return

    t = RichTable(box=box.SIMPLE_HEAD, header_style="bold dim", show_edge=False, padding=(0, 1))
    t.add_column("student",  style="bold")
    t.add_column("avg",      justify="right")
    t.add_column("missing",  justify="right", style="dim")
    t.add_column("risk")
    t.add_column("reason",   style="dim")

    for r in sorted(at_risk, key=lambda x: x.get("avg", 0)):
        risk_style = "bold red" if r["risk"] == "HIGH" else "yellow"
        t.add_row(
            str(r["student"]),
            f"{float(r.get('avg') or 0):.1f}%",
            str(r.get("missing", 0)),
            Text(r["risk"], style=risk_style),
            r["reason"],
        )

    console.print(t)
    console.print()

    # Summary bar
    high   = sum(1 for r in at_risk if r["risk"] == "HIGH")
    medium = sum(1 for r in at_risk if r["risk"] == "MEDIUM")
    total  = len(student_avgs)
    low    = total - high - medium

    console.print(Rule("[dim]RISK SUMMARY[/dim]", style="dim", align="left"))
    console.print()
    max_v = max(high, medium, low) or 1
    bar_w = 20
    for label, count, style in [("HIGH", high, "bold red"), ("MEDIUM", medium, "yellow"), ("LOW", low, "green")]:
        bar  = "#" * max(0, int(count / max_v * bar_w))
        line = Text(f"  {label:<6}  ")
        line.append(f"{bar:<{bar_w}}", style=style)
        line.append(f"  {count}")
        console.print(line)
    console.print()


def render_score_distribution(
    scores: list[float],
    assignment: str = "",
    title: str = "",
) -> None:
    """Histogram of scores grouped into 10-point grade bands."""
    if not scores:
        console.print("[dim]No data[/dim]")
        return

    title = title or f"SCORE DISTRIBUTION{': ' + assignment if assignment else ''}"

    bands = [
        ("0–49",   0,  50),
        ("50–59",  50, 60),
        ("60–69",  60, 70),
        ("70–79",  70, 80),
        ("80–89",  80, 90),
        ("90–100", 90, 101),
    ]
    counts = {label: sum(1 for s in scores if lo <= s < hi) for label, lo, hi in bands}
    max_c  = max(counts.values()) or 1
    bar_w  = 24

    avg    = sum(scores) / len(scores)
    sorted_s = sorted(scores)
    median = sorted_s[len(sorted_s) // 2]

    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
    console.print()

    for label, lo, _ in bands:
        count  = counts[label]
        bar    = "#" * max(0, int(count / max_c * bar_w))
        style  = "green" if lo >= 70 else ("yellow" if lo >= 60 else "red")
        line   = Text(f"  {label:<7}  ")
        line.append(f"{bar:<{bar_w}}", style=style)
        line.append(f"  {count}")
        console.print(line)

    console.print()
    console.print(f"  [dim]average:[/dim]  {avg:.1f}%")
    console.print(f"  [dim]median: [/dim]  {median:.1f}%")
    console.print()


def render_missing_work(
    rows: list[dict],
    title: str = "MISSING SUBMISSIONS",
) -> None:
    """rows: [{"student": ..., "assignment": ..., "topic": ...}]"""
    if not rows:
        console.print("  [green]No missing submissions.[/green]")
        console.print()
        return

    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
    console.print()

    t = RichTable(box=box.SIMPLE_HEAD, header_style="bold dim", show_edge=False, padding=(0, 1))
    t.add_column("student",    style="bold")
    t.add_column("assignment", style="dim")
    if any(r.get("topic") for r in rows):
        t.add_column("topic", style="dim")
        for r in rows:
            t.add_row(str(r.get("student", "")), str(r.get("assignment", "")), str(r.get("topic") or "—"))
    else:
        for r in rows:
            t.add_row(str(r.get("student", "")), str(r.get("assignment", "")))

    console.print(t)
    console.print()

    # Summary: count per student
    by_student: dict[str, int] = {}
    for r in rows:
        s = str(r.get("student", ""))
        by_student[s] = by_student.get(s, 0) + 1

    if len(by_student) > 1:
        console.print(Rule("[dim]BY STUDENT[/dim]", style="dim", align="left"))
        console.print()
        for s, n in sorted(by_student.items(), key=lambda x: -x[1]):
            console.print(f"  [bold]{s}[/bold]  [dim]{n} missing[/dim]")
        console.print()


def render_topic_mastery(
    items: list[dict],
    reteach_threshold: float = 70.0,
    title: str = "TOPIC MASTERY",
) -> None:
    """items: [{"topic": str, "avg": float, "pass_rate": float, "count": int}]"""
    if not items:
        console.print("[dim]No topic data[/dim]")
        return

    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
    console.print()

    t = RichTable(box=box.SIMPLE_HEAD, header_style="bold dim", show_edge=False, padding=(0, 1))
    t.add_column("topic",     style="bold")
    t.add_column("avg",       justify="right")
    t.add_column("pass rate", justify="right", style="dim")
    t.add_column("students",  justify="right", style="dim")
    t.add_column("chart")

    bar_w = 20
    max_avg = max(r["avg"] for r in items) or 1
    reteach_list = []
    for r in items:
        avg       = float(r["avg"])
        pass_rate = float(r.get("pass_rate") or 0)
        count     = int(r.get("count") or 0)
        bar       = "#" * max(1, int(avg / 100 * bar_w))
        style     = "green" if avg >= reteach_threshold else ("yellow" if avg >= 60 else "red")
        t.add_row(
            str(r["topic"]),
            Text(f"{avg:.1f}%", style=style),
            f"{pass_rate:.1f}%",
            str(count),
            Text(f"{bar:<{bar_w}}", style=style),
        )
        if avg < reteach_threshold:
            reteach_list.append((str(r["topic"]), avg))

    console.print(t)

    if reteach_list:
        console.print()
        console.print(Rule("[dim]NEEDS RETEACHING[/dim]", style="dim", align="left"))
        console.print()
        for i, (topic, avg) in enumerate(sorted(reteach_list, key=lambda x: x[1]), 1):
            console.print(f"  [red]{i}.[/red]  [bold]{topic}[/bold]  [dim]{avg:.1f}%[/dim]")
    console.print()


def render_assignment_difficulty(
    items: list[dict],
    title: str = "ASSIGNMENT DIFFICULTY",
) -> None:
    """items: [{"assignment", "avg", "median", "pass_rate", "submitted", "missing"}]"""
    if not items:
        console.print("[dim]No data[/dim]")
        return

    def _difficulty(avg: float) -> Text:
        if avg >= 80:
            return Text("easy",   style="green")
        if avg >= 65:
            return Text("normal", style="dim")
        return Text("hard", style="red")

    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
    console.print()

    t = RichTable(box=box.SIMPLE_HEAD, header_style="bold dim", show_edge=False, padding=(0, 1))
    t.add_column("assignment", style="bold")
    t.add_column("avg",        justify="right")
    t.add_column("median",     justify="right", style="dim")
    t.add_column("pass rate",  justify="right")
    t.add_column("missing",    justify="right", style="dim")
    t.add_column("difficulty")

    for r in sorted(items, key=lambda x: float(x.get("avg") or 0), reverse=True):
        avg  = float(r.get("avg") or 0)
        med  = float(r.get("median") or 0)
        pr   = float(r.get("pass_rate") or 0)
        miss = int(r.get("missing") or 0)
        t.add_row(
            str(r["assignment"]),
            f"{avg:.1f}%",
            f"{med:.1f}%",
            Text(f"{pr:.1f}%", style="green" if pr >= 70 else "red"),
            str(miss),
            _difficulty(avg),
        )

    console.print(t)

    hardest = min(items, key=lambda x: float(x.get("avg") or 100))
    console.print()
    console.print(f"  [dim]hardest:[/dim]  [bold]{hardest['assignment']}[/bold]"
                  f"  [red]{float(hardest.get('avg') or 0):.1f}%[/red]")
    console.print()


def render_progress_trend(
    items: list[dict],
    student: str = "",
    reteach_threshold: float = 70.0,
    title: str = "",
) -> None:
    """items: [{"assignment": str, "date": str, "avg": float}] sorted chronologically."""
    if not items:
        console.print("[dim]No data[/dim]")
        return

    title = title or (f"PROGRESS TREND: {student}" if student else "CLASS PROGRESS TREND")
    bar_w = 20

    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
    console.print()

    lw = max(len(str(r["assignment"])) for r in items)
    for r in items:
        avg   = float(r.get("avg") or 0)
        bar   = "#" * max(1, int(avg / 100 * bar_w))
        style = "green" if avg >= reteach_threshold else ("yellow" if avg >= 60 else "red")
        line  = Text(f"  {str(r['assignment']):<{lw}}  ")
        line.append(f"{bar:<{bar_w}}", style=style)
        line.append(f"  {avg:.1f}%")
        console.print(line)

    avgs = [float(r.get("avg") or 0) for r in items]
    if len(avgs) >= 2:
        trend = avgs[-1] - avgs[0]
        direction = "improving" if trend > 2 else ("declining" if trend < -2 else "stable")
        style = "green" if direction == "improving" else ("red" if direction == "declining" else "dim")
        console.print()
        console.print(f"  [dim]trend:[/dim]  [{style}]{direction}[/{style}]"
                      f"  [dim]({avgs[0]:.1f}% → {avgs[-1]:.1f}%)[/dim]")
    console.print()


def render_reteach(
    items: list[dict],
    title: str = "RETEACH QUEUE",
) -> None:
    """items: [{"topic": str, "avg": float, "pass_rate": float, "priority": str}]"""
    if not items:
        console.print("  [green]No topics need reteaching.[/green]")
        console.print()
        return

    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
    console.print()

    t = RichTable(box=box.SIMPLE_HEAD, header_style="bold dim", show_edge=False, padding=(0, 1))
    t.add_column("priority", style="bold")
    t.add_column("topic")
    t.add_column("reason", style="dim")

    for r in items:
        avg       = float(r.get("avg") or 0)
        pass_rate = float(r.get("pass_rate") or 0)
        priority  = str(r.get("priority", "MEDIUM"))
        reason    = f"avg {avg:.1f}%, pass rate {pass_rate:.1f}%"
        style     = "bold red" if priority == "HIGH" else ("yellow" if priority == "MEDIUM" else "dim")
        t.add_row(Text(priority, style=style), str(r["topic"]), reason)

    console.print(t)

    top = items[0]
    console.print()
    console.print(f"  [dim]suggested next lesson:[/dim]  "
                  f"Review [bold]{top['topic']}[/bold] — "
                  f"avg {float(top.get('avg') or 0):.1f}%")
    console.print()


def render_teacher_report(
    summary_rows: list[dict],
    topic_items: list[dict],
    assignment_items: list[dict],
    at_risk_list: list[dict],
    missing_rows: list[dict],
    score_col: str = "score",
    max_score_col: str = "max_score",
    student_col: str = "student",
    assignment_col: str = "assignment",
    topic_col: str = "topic",
    title: str = "TEACHER REPORT",
) -> None:
    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
    console.print()

    # Summary stats inline (no sub-rule headers, keep it tight)
    render_teacher_summary(summary_rows, score_col=score_col, max_score_col=max_score_col,
                           student_col=student_col, assignment_col=assignment_col,
                           topic_col=topic_col, title="SUMMARY")

    if topic_items:
        reteach_items = [
            {"topic": r["topic"], "avg": r["avg"], "pass_rate": r.get("pass_rate", 0),
             "priority": "HIGH" if float(r["avg"]) < 60 else "MEDIUM"}
            for r in topic_items if float(r["avg"]) < 70
        ]
        render_topic_mastery(topic_items, title="TOPIC MASTERY")
        if reteach_items:
            render_reteach(reteach_items, title="RETEACH QUEUE")

    if assignment_items:
        render_assignment_difficulty(assignment_items, title="ASSIGNMENT DIFFICULTY")

    if at_risk_list:
        render_at_risk(at_risk_list, title="AT RISK")

    if missing_rows:
        render_missing_work(missing_rows, title="MISSING SUBMISSIONS")
