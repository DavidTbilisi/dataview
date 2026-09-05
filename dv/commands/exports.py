"""Diffing, saved views, and file export commands."""

import difflib

from pathlib import Path

import typer

from dv.app import (
    app,
    ds as _ds,
    config,
    where as _where,
)
from dv.core.detect import make_datasource
from dv.core.errors import DvError
from dv.core.query import run_query, require_columns
from dv.core.schema import get_schema
from dv.core.sql import ident, agg_expr
from dv.core.stats import get_summary
from dv.render.theme import charset, console
from dv.render.diff import render_diff
from dv.render.export import export_markdown, export_html
from dv.render.table import render_table
from dv.render.charts import render_bar


@app.command()
def diff(
    other: Path = typer.Argument(..., help="Second file to compare against"),
    key: str = typer.Option(..., "--key", help="Key column for row matching"),
):
    """Compare this file against another file row by row."""
    ds_a = _ds()
    if not other.exists():
        raise DvError(f"File not found: {other}")
    # The filter names the data dv is looking at, so it applies to both sides.
    ds_b = make_datasource(other, where=_where())
    require_columns(ds_a, key)
    require_columns(ds_b, key)

    result_a = run_query(ds_a, "SELECT * FROM data")
    result_b = run_query(ds_b, "SELECT * FROM data")
    cols = result_a.columns
    render_diff(
        result_a.rows,
        result_b.rows,
        key=key,
        columns=cols,
        title=f"DIFF: {ds_a.path.name} {charset().arrow} {other.name}",
    )


def _report_data(ds):
    """Schema, summary and one categorical chart — shared by both exporters."""
    schema_info = get_schema(ds)
    stats = get_summary(ds, schema_info)   # reuse the schema instead of recomputing

    chart_rows = []
    for col in schema_info.columns:
        if col.inferred_type == "text" and col.unique <= 30:
            result = run_query(
                ds,
                f"SELECT {ident(col.name)}, count(*) AS count FROM data "
                f"GROUP BY {ident(col.name)} ORDER BY count DESC LIMIT 20",
            )
            chart_rows.append((col.name, [(r[col.name], r["count"]) for r in result.rows]))
            break

    return schema_info, stats, chart_rows or None


@app.command(name="export-md")
def export_md(output: Path = typer.Argument(..., help="Output markdown file")):
    """Export a Markdown report of the file."""
    ds = _ds()
    export_markdown(output, *_report_data(ds), where=_where())
    console.print(f"[green]OK[/green] wrote {output}")


@app.command(name="export-html")
def export_html_cmd(output: Path = typer.Argument(..., help="Output HTML file")):
    """Export a self-contained HTML report of the file."""
    ds = _ds()
    export_html(output, *_report_data(ds), where=_where())
    console.print(f"[green]OK[/green] wrote {output}")


@app.command()
def alias(name: str = typer.Argument(..., help="Alias name defined in .dv.yml")):
    """Run a saved view from the `aliases` section of .dv.yml."""
    ds = _ds()
    cfg = config()
    if not cfg.aliases:
        raise DvError(
            "No aliases defined",
            hint=f"Add an `aliases:` section to {cfg.path or '.dv.yml'}",
        )
    spec = cfg.aliases.get(name)
    if spec is None:
        close = difflib.get_close_matches(name, list(cfg.aliases), n=1, cutoff=0.5)
        hint = (f"Did you mean {close[0]!r}?" if close
                else f"Defined: {', '.join(sorted(cfg.aliases))}")
        raise DvError(f"Unknown alias {name!r}", hint=hint)
    if not isinstance(spec, dict):
        raise DvError(f"Alias {name!r} must be a mapping of options")

    group_col = spec.get("group_by")
    if not group_col:
        raise DvError(f"Alias {name!r} needs a `group_by:` key",
                      hint="e.g.  money:\n    group_by: category\n    sum: amount")
    sum_col = spec.get("sum")
    avg_col = spec.get("avg")
    limit = int(spec.get("limit", 20))
    require_columns(ds, group_col, sum_col, avg_col)

    agg, value_col, label = agg_expr(sum_col, avg_col)
    g = ident(group_col)
    result = run_query(
        ds,
        f"SELECT {g}, {agg} FROM data GROUP BY {g} "
        f"ORDER BY {ident(value_col)} DESC LIMIT {int(limit)}",
    )
    render_table(result, title=f"alias: {name}")
    if spec.get("bar", True) and result.rows:
        render_bar([(str(r[group_col]), float(r[value_col] or 0)) for r in result.rows],
                   title=f"{label} by {group_col}")
