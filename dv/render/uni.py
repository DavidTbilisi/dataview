from rich.console import Console
from rich.rule import Rule
from rich.table import Table as RichTable
from rich.text import Text
from rich import box

console = Console()

_GRADE_SCALE = [
    (90, "A",  4.0), (87, "A-", 3.7), (83, "B+", 3.3), (80, "B",  3.0),
    (77, "B-", 2.7), (73, "C+", 2.3), (70, "C",  2.0), (67, "C-", 1.7),
    (63, "D+", 1.3), (60, "D",  1.0), (0,  "F",  0.0),
]

_DONE_STATUSES = {"done", "completed", "passed", "complete"}
_FAIL_STATUSES = {"failed", "fail", "retake", "f"}
_ACTIVE_STATUSES = {"active", "doing", "in-progress", "inprogress", "current"}


def _grade_from_score(score: float) -> tuple[str, float]:
    for threshold, letter, points in _GRADE_SCALE:
        if score >= threshold:
            return letter, points
    return "F", 0.0


def _bar(v: float, max_v: float, width: int = 20) -> str:
    if max_v <= 0:
        return ""
    return "#" * max(1, int(v / max_v * width))


def render_uni_summary(
    rows: list[dict],
    course_col:   str = "course",
    credits_col:  str = "credits",
    semester_col: str = "semester",
    status_col:   str = "status",
    score_col:    str = "score",
    title:        str = "UNIVERSITY SUMMARY",
) -> None:
    if not rows:
        console.print("[dim]No data[/dim]")
        return

    done     = [r for r in rows if str(r.get(status_col, "")).lower() in _DONE_STATUSES]
    failed   = [r for r in rows if str(r.get(status_col, "")).lower() in _FAIL_STATUSES]
    active   = [r for r in rows if str(r.get(status_col, "")).lower() in _ACTIVE_STATUSES]

    total_credits    = sum(float(r.get(credits_col) or 0) for r in rows)
    done_credits     = sum(float(r.get(credits_col) or 0) for r in done)
    active_credits   = sum(float(r.get(credits_col) or 0) for r in active)
    scored           = [float(r[score_col]) for r in done if r.get(score_col) is not None]
    avg_score        = sum(scored) / len(scored) if scored else 0.0

    # GPA from completed (excluding in-progress)
    gpa_rows = done + failed
    gpa_num = gpa_den = 0.0
    for r in gpa_rows:
        sc = r.get(score_col)
        cr = float(r.get(credits_col) or 0)
        if sc is not None and cr > 0:
            _, gp = _grade_from_score(float(sc))
            gpa_num += gp * cr
            gpa_den += cr
    gpa = gpa_num / gpa_den if gpa_den else 0.0

    semesters = sorted({str(r.get(semester_col, "")) for r in rows if r.get(semester_col)})
    current   = semesters[-1] if semesters else ""

    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
    console.print()

    if current:
        console.print(f"  [dim]current semester:[/dim]  {current}")
        console.print()

    pairs = [
        ("courses",      str(len(rows))),
        ("total credits", f"{total_credits:.0f}"),
        ("done",         f"{len(done)}  ({done_credits:.0f} cr)"),
        ("active",       f"{len(active)}  ({active_credits:.0f} cr)"),
        ("failed",       f"{len(failed)}"),
        ("avg score",    f"{avg_score:.1f}%" if scored else "—"),
        ("GPA estimate", f"{gpa:.2f} / 4.00"),
    ]
    kw = max(len(k) for k, _ in pairs)
    for k, v in pairs:
        console.print(f"  [dim]{k.ljust(kw)}[/dim]  {v}")

    console.print()
    console.print(Rule("[dim]STATUS[/dim]", style="dim", align="left"))
    console.print()
    max_c = max(len(done), len(active), len(failed)) or 1
    bar_w = 20
    for label, count, style in [("done", len(done), "green"), ("active", len(active), "cyan"), ("failed", len(failed), "red")]:
        bar  = "#" * max(0, int(count / max_c * bar_w))
        line = Text(f"  {label:<6}  ")
        line.append(f"{bar:<{bar_w}}", style=style)
        line.append(f"  {count}")
        console.print(line)
    console.print()


def render_gpa(
    rows: list[dict],
    course_col:  str = "course",
    credits_col: str = "credits",
    status_col:  str = "status",
    score_col:   str = "score",
    title:       str = "GRADES",
) -> None:
    if not rows:
        console.print("[dim]No data[/dim]")
        return

    gradable = [r for r in rows
                if str(r.get(status_col, "")).lower() in (_DONE_STATUSES | _FAIL_STATUSES)
                and r.get(score_col) is not None]

    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
    console.print()

    t = RichTable(box=box.SIMPLE_HEAD, header_style="bold dim", show_edge=False, padding=(0, 1))
    t.add_column(course_col, style="bold")
    t.add_column(credits_col, justify="right", style="dim")
    t.add_column("score",   justify="right")
    t.add_column("grade",   justify="right")
    t.add_column("points",  justify="right", style="dim")

    gpa_num = gpa_den = 0.0
    band_counts = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}

    for r in sorted(gradable, key=lambda x: float(x.get(score_col) or 0), reverse=True):
        sc   = float(r[score_col])
        cr   = float(r.get(credits_col) or 0)
        letter, gp = _grade_from_score(sc)
        gpa_num += gp * cr
        gpa_den += cr
        style = "green" if sc >= 70 else "red"
        t.add_row(
            str(r.get(course_col, "")),
            str(int(cr)),
            Text(f"{sc:.1f}%", style=style),
            Text(letter, style=style),
            f"{gp:.1f}",
        )
        band_counts[letter[0]] = band_counts.get(letter[0], 0) + 1

    gpa = gpa_num / gpa_den if gpa_den else 0.0
    console.print(t)
    console.print()
    style = "green" if gpa >= 3.0 else ("yellow" if gpa >= 2.0 else "red")
    console.print(f"  [dim]GPA estimate:[/dim]  [{style}]{gpa:.2f} / 4.00[/{style}]")
    console.print()

    console.print(Rule("[dim]GRADE DISTRIBUTION[/dim]", style="dim", align="left"))
    console.print()
    max_b = max(band_counts.values()) or 1
    bar_w = 20
    for band, bstyle in [("A", "green"), ("B", "cyan"), ("C", "yellow"), ("D", "dim"), ("F", "red")]:
        count = band_counts.get(band, 0)
        bar   = "#" * max(0, int(count / max_b * bar_w))
        line  = Text(f"  {band}  ")
        line.append(f"{bar:<{bar_w}}", style=bstyle)
        line.append(f"  {count}")
        console.print(line)
    console.print()


def render_semester_progress(
    rows: list[dict],
    semester: str = "",
    course_col:  str = "course",
    credits_col: str = "credits",
    status_col:  str = "status",
    score_col:   str = "score",
    title:       str = "",
) -> None:
    if not rows:
        console.print("[dim]No data[/dim]")
        return

    title = title or f"SEMESTER PROGRESS{': ' + semester if semester else ''}"

    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
    console.print()

    t = RichTable(box=box.SIMPLE_HEAD, header_style="bold dim", show_edge=False, padding=(0, 1))
    t.add_column(course_col,  style="bold")
    t.add_column(credits_col, justify="right", style="dim")
    t.add_column("status")
    t.add_column("score",    justify="right")
    t.add_column("progress", min_width=20)

    total_cr = done_cr = 0.0
    bar_w = 20

    for r in sorted(rows, key=lambda x: (str(x.get(status_col, "")), str(x.get(course_col, "")))):
        cr     = float(r.get(credits_col) or 0)
        sc     = r.get(score_col)
        status = str(r.get(status_col, "")).lower()
        total_cr += cr

        if status in _DONE_STATUSES:
            done_cr += cr
            sc_f    = float(sc) if sc is not None else 0.0
            filled  = max(1, int(sc_f / 100 * bar_w))
            bar     = "#" * filled + "-" * (bar_w - filled)
            bstyle  = "green" if sc_f >= 70 else "red"
            prog    = Text(f"{bar}", style=bstyle)
            sstyle  = "green"
        elif status in _FAIL_STATUSES:
            sc_f   = float(sc) if sc is not None else 0.0
            filled = max(1, int(sc_f / 100 * bar_w))
            bar    = "x" * filled + "-" * (bar_w - filled)
            prog   = Text(f"{bar}", style="red")
            sstyle = "red"
        else:
            sc_f   = float(sc) if sc is not None else 0.0
            if sc_f > 0:
                filled = max(1, int(sc_f / 100 * bar_w))
                bar    = "#" * filled + "-" * (bar_w - filled)
            else:
                bar = "-" * bar_w
            prog   = Text(f"{bar}", style="cyan")
            sstyle = "cyan"

        sc_str = f"{sc_f:.1f}%" if sc is not None else "—"
        t.add_row(
            str(r.get(course_col, "")),
            str(int(cr)),
            Text(status, style=sstyle),
            sc_str,
            prog,
        )

    console.print(t)
    console.print()

    pct = done_cr / total_cr * 100 if total_cr else 0
    bar_w2 = 30
    filled = int(pct / 100 * bar_w2)
    bar    = "#" * filled + "-" * (bar_w2 - filled)
    console.print(f"  [dim]credits completed:[/dim]  {done_cr:.0f} / {total_cr:.0f}")
    style  = "green" if pct >= 70 else ("yellow" if pct >= 40 else "cyan")
    line   = Text(f"  progress          [")
    line.append(bar, style=style)
    line.append(f"]  {pct:.1f}%")
    console.print(line)
    console.print()
