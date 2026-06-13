from rich.console import Console
from rich.rule import Rule
from rich.text import Text

console = Console()


def render_box(
    values: list[float],
    title: str = "",
    width: int = 60,
) -> None:
    if len(values) < 4:
        console.print("[dim]Not enough data for box plot[/dim]")
        return

    sv = sorted(values)
    n  = len(sv)
    mn = sv[0]
    mx = sv[-1]
    q1 = sv[n // 4]
    med = sv[n // 2]
    q3  = sv[3 * n // 4]

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
        console.print(Rule(f"[bold]{title}[/bold]", style="dim", align="left"))
        console.print()

    pairs = [("min", fmt(mn)), ("q1", fmt(q1)), ("median", fmt(med)),
             ("q3", fmt(q3)), ("max", fmt(mx))]
    kw = max(len(k) for k, _ in pairs)
    for k, v in pairs:
        console.print(f"  [dim]{k.ljust(kw)}[/dim]  {v}")
    console.print()

    chars = [" "] * width
    for i in range(p_min, p_q1):
        chars[i] = "─"
    for i in range(p_q3, p_max + 1):
        chars[i] = "─"
    for i in range(p_q1, p_q3 + 1):
        chars[i] = "═"
    chars[p_min] = "├"
    chars[p_max] = "┤"
    chars[p_q1]  = "┠"
    chars[p_q3]  = "┨"
    chars[p_med] = "┃"

    line = Text("  ")
    for ch in chars:
        if ch == "═":
            line.append(ch, style="cyan")
        elif ch in ("┃", "┠", "┨"):
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
