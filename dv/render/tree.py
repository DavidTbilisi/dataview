from rich.console import Console
from rich.tree import Tree

console = Console()


def render_tree(rows: list[dict], path_cols: list[str]) -> None:
    if not rows:
        console.print("[dim]No data[/dim]")
        return

    root = Tree("[bold cyan]Root[/bold cyan]")
    nodes: dict[tuple, Tree] = {(): root}

    paths = []
    for row in rows:
        parts = tuple(str(row.get(c, "?")) for c in path_cols)
        paths.append(parts)

    seen = set()
    for parts in sorted(paths):
        for i in range(len(parts)):
            prefix = parts[: i + 1]
            if prefix not in seen:
                seen.add(prefix)
                parent = nodes[parts[:i]]
                child = parent.add(parts[i])
                nodes[prefix] = child

    console.print(root)
