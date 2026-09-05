from dv.render.json_out import emit, json_mode
from dv.render.theme import charset, console


def _guides() -> tuple[str, str, str, str]:
    """(branch, last branch, vertical continuation, blank) for the active charset."""
    if charset().name == "ascii":
        return "|-- ", "`-- ", "|   ", "    "
    return "├── ", "└── ", "│   ", "    "


def render_tree(rows: list[dict], path_cols: list[str], root_label: str = "Root") -> None:
    if json_mode():
        emit("rows", rows)
        return

    if not rows:
        console.print("[dim]No data[/dim]")
        return

    # Nested dict keyed by path segment, preserving sorted order.
    tree: dict = {}
    for row in rows:
        node = tree
        for col in path_cols:
            key = str(row.get(col, "?"))
            node = node.setdefault(key, {})

    branch, last, pipe, blank = _guides()

    def walk(node: dict, prefix: str) -> None:
        items = sorted(node.items())
        for i, (name, children) in enumerate(items):
            is_last = i == len(items) - 1
            console.print(f"{prefix}[dim]{last if is_last else branch}[/dim]{name}")
            if children:
                walk(children, prefix + (blank if is_last else f"[dim]{pipe}[/dim]"))

    console.print()
    console.print(f"[bold cyan]{root_label}[/bold cyan]")
    walk(tree, "")
    console.print()
