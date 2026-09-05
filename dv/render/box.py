from rich.text import Text
from dv.core.stats import BoxStats
from dv.render.common import kv_pairs, rule
from dv.render.json_out import emit, json_mode
from dv.render.theme import charset, console


def render_box(
    stats: BoxStats | None,
    title: str = "",
    width: int = 60,
) -> None:
    """Draw a five-number summary. See `core.stats.box_stats` for the maths."""
    if json_mode():
        emit("box", None if stats is None else {
            "count": stats.count, "min": stats.min, "q1": stats.q1,
            "median": stats.median, "q3": stats.q3, "max": stats.max,
        })
        return

    if stats is None:
        console.print("[dim]Not enough data for box plot[/dim]")
        return

    mn, q1, med, q3, mx = stats.min, stats.q1, stats.median, stats.q3, stats.max
    rng = mx - mn or 1.0

    def pos(v: float) -> int:
        return min(int((v - mn) / rng * (width - 1)), width - 1)

    p_min = 0
    p_q1  = pos(q1)
    p_med = pos(med)
    p_q3  = pos(q3)
    p_max = width - 1

    def fmt(v: float) -> str:
        return f"{v:g}"

    if title:
        console.print()
        console.print(rule(f"[bold]{title}[/bold]", style="dim", align="left"))
        console.print()

    kv_pairs([("min", fmt(mn)), ("q1", fmt(q1)), ("median", fmt(med)),
              ("q3", fmt(q3)), ("max", fmt(mx))])
    console.print()

    cs = charset()
    chars = [" "] * width
    for i in range(p_min, p_q1):
        chars[i] = cs.whisker
    for i in range(p_q3, p_max + 1):
        chars[i] = cs.whisker
    for i in range(p_q1, p_q3 + 1):
        chars[i] = cs.fence
    chars[p_min] = cs.box_left if cs.name == "ascii" else "├"
    chars[p_max] = cs.box_right if cs.name == "ascii" else "┤"
    chars[p_q1]  = cs.box_left
    chars[p_q3]  = cs.box_right
    chars[p_med] = cs.median

    emphatic = {cs.median, cs.box_left, cs.box_right}
    line = Text("  ")
    for ch in chars:
        if ch == cs.fence:
            line.append(ch, style="cyan")
        elif ch in emphatic:
            line.append(ch, style="bold cyan")
        else:
            line.append(ch, style="dim")
    console.print(line)

    # Tick labels
    label_chars = [" "] * width

    def place(p: int, label: str) -> None:
        start = max(0, min(p - len(label) // 2, width - len(label)))
        for i, ch in enumerate(label):
            if start + i < width:
                label_chars[start + i] = ch

    place(p_min, fmt(mn))
    place(p_q1,  fmt(q1))
    place(p_med, fmt(med))
    place(p_q3,  fmt(q3))
    place(p_max, fmt(mx))

    console.print(Text("  " + "".join(label_chars), style="dim"))
    console.print()
