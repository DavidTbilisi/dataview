from rich.console import Console
from rich.rule import Rule
from rich.table import Table as RichTable
from rich import box

console = Console()


def _fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def render_diff(
    rows_a: list[dict],
    rows_b: list[dict],
    key: str,
    columns: list[str],
    title: str = "",
) -> None:
    dict_a = {str(r[key]): r for r in rows_a if r.get(key) is not None}
    dict_b = {str(r[key]): r for r in rows_b if r.get(key) is not None}

    keys_a = set(dict_a)
    keys_b = set(dict_b)

    added_keys   = keys_b - keys_a
    removed_keys = keys_a - keys_b
    common_keys  = keys_a & keys_b

    changed: list[tuple[str, list[tuple[str, str, str]]]] = []
    for k in sorted(common_keys):
        ra, rb = dict_a[k], dict_b[k]
        diffs = [
            (col, _fmt(ra.get(col)), _fmt(rb.get(col)))
            for col in columns
            if col != key and str(ra.get(col)) != str(rb.get(col))
        ]
        if diffs:
            changed.append((k, diffs))

    _title = title or "DIFF"
    console.print()
    console.print(Rule(f"[bold]{_title}[/bold]", style="dim", align="left"))
    console.print()
    console.print(f"  [green]Added:[/green]    {len(added_keys)}")
    console.print(f"  [red]Removed:[/red]   {len(removed_keys)}")
    console.print(f"  [yellow]Changed:[/yellow]   {len(changed)}")
    console.print()

    if changed:
        console.print(Rule("[dim]changed[/dim]", style="dim", align="left"))
        console.print()
        t = RichTable(box=box.SIMPLE_HEAD, header_style="bold dim", show_edge=False, padding=(0, 1))
        t.add_column(key,      style="bold")
        t.add_column("field")
        t.add_column("before", style="red dim")
        t.add_column("after",  style="green")
        for k, diffs in changed:
            for i, (col, va, vb) in enumerate(diffs):
                t.add_row(k if i == 0 else "", col, va, vb)
        console.print(t)
        console.print()

    non_key = [c for c in columns if c != key][:5]

    if added_keys:
        console.print(Rule("[dim]added[/dim]", style="dim", align="left"))
        console.print()
        t = RichTable(box=box.SIMPLE_HEAD, header_style="bold dim", show_edge=False, padding=(0, 1))
        t.add_column(key, style="green bold")
        for c in non_key:
            t.add_column(c)
        for k in sorted(added_keys):
            r = dict_b[k]
            t.add_row(k, *[_fmt(r.get(c)) for c in non_key])
        console.print(t)
        console.print()

    if removed_keys:
        console.print(Rule("[dim]removed[/dim]", style="dim", align="left"))
        console.print()
        t = RichTable(box=box.SIMPLE_HEAD, header_style="bold dim", show_edge=False, padding=(0, 1))
        t.add_column(key, style="red bold")
        for c in non_key:
            t.add_column(c)
        for k in sorted(removed_keys):
            r = dict_a[k]
            t.add_row(k, *[_fmt(r.get(c)) for c in non_key])
        console.print(t)
        console.print()
