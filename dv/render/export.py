from html import escape
from pathlib import Path

from dv.core.schema import SchemaInfo
from dv.core.stats import SummaryStats
from dv.render.theme import ASCII


def _ascii_bar(value: float, max_value: float, width: int = 40) -> str:
    """Exports are always plain ASCII, regardless of the terminal charset."""
    return ASCII.bar_of(value, max_value, width)


def _schema_md(schema: SchemaInfo) -> str:
    lines = ["## Schema\n", f"Rows: {schema.row_count}  \n", f"Columns: {len(schema.columns)}\n\n"]
    lines.append("| Column | Type | Missing | Unique |\n")
    lines.append("|--------|------|---------|--------|\n")
    for col in schema.columns:
        lines.append(f"| {col.name} | {col.inferred_type} | {col.missing} | {col.unique} |\n")
    return "".join(lines)


def _summary_md(stats: SummaryStats) -> str:
    lines = ["## Summary\n\n"]
    lines.append(f"- File: {Path(stats.path).name}\n")
    lines.append(f"- Format: {stats.format.upper()}\n")
    lines.append(f"- Rows: {stats.row_count}\n")
    lines.append(f"- Columns: {stats.col_count}\n")
    lines.append(f"- Missing values: {stats.missing_total}\n")
    lines.append(f"- Duplicate rows: {stats.duplicate_count}\n\n")

    if stats.numeric_stats:
        lines.append("### Numeric Summary\n\n")
        lines.append("| Column | Count | Min | Max | Mean | Median |\n")
        lines.append("|--------|-------|-----|-----|------|--------|\n")
        for ns in stats.numeric_stats:
            lines.append(
                f"| {ns.column} | {ns.count} | {ns.min:.2f} | {ns.max:.2f} | {ns.mean:.2f} | {ns.median:.2f} |\n"
            )
        lines.append("\n")
    return "".join(lines)


def _bar_md(rows: list[tuple[str, int | float]], title: str, width: int = 40) -> str:
    if not rows:
        return ""
    max_val = max(v for _, v in rows)
    lines = [f"### {title}\n\n```text\n"]
    label_width = max(len(str(k)) for k, _ in rows)
    for label, value in rows:
        bar = _ascii_bar(float(value), float(max_val), width=width)
        val_str = f"{value:.2f}" if isinstance(value, float) else str(value)
        lines.append(f"{str(label).ljust(label_width)}  {bar}  {val_str}\n")
    lines.append("```\n\n")
    return "".join(lines)


def export_markdown(
    path: Path,
    schema: SchemaInfo,
    stats: SummaryStats,
    chart_rows: list[tuple[str, list[tuple[str, int | float]]]] | None = None,
    where: str | None = None,
) -> None:
    name = Path(schema.path).name
    lines = [f"# Data Report: {name}\n\n"]
    # A filtered report looks like a full one once it is saved, so say so.
    if where:
        lines.append(f"Filtered by: `{where}`\n\n")
    lines.append(_summary_md(stats))
    lines.append(_schema_md(schema))
    lines.append("\n")

    if chart_rows:
        for title, rows in chart_rows:
            lines.append(_bar_md(rows, title))

    path.write_text("".join(lines))


_HTML_CSS = """
:root { color-scheme: light dark; }
body { margin: 2rem auto; max-width: 60rem; padding: 0 1rem;
       font: 14px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
h1, h2, h3 { font-weight: 600; line-height: 1.25; }
h1 { font-size: 1.6rem; } h2 { font-size: 1.2rem; margin-top: 2rem; }
h3 { font-size: 1rem; }
pre { overflow-x: auto; padding: 1rem; border-radius: 6px;
      background: rgba(127,127,127,.12); }
table { border-collapse: collapse; margin: 1rem 0; }
th, td { text-align: left; padding: .3rem .8rem; border-bottom: 1px solid rgba(127,127,127,.3); }
th { font-weight: 600; }
td:not(:first-child), th:not(:first-child) { text-align: right; }
"""


def _schema_html(schema: SchemaInfo) -> str:
    rows = "".join(
        f"<tr><td>{c.name}</td><td>{c.inferred_type}</td>"
        f"<td>{c.missing}</td><td>{c.unique}</td></tr>"
        for c in schema.columns
    )
    return (
        "<h2>Schema</h2>\n<table>\n"
        "<tr><th>Column</th><th>Type</th><th>Missing</th><th>Unique</th></tr>\n"
        f"{rows}\n</table>\n"
    )


def _summary_html(stats: SummaryStats) -> str:
    pairs = [
        ("File", Path(stats.path).name),
        ("Format", stats.format.upper()),
        ("Rows", stats.row_count),
        ("Columns", stats.col_count),
        ("Missing values", stats.missing_total),
        ("Duplicate rows", stats.duplicate_count),
    ]
    if stats.date_range:
        pairs.append(("Date range", f"{stats.date_range[0]} to {stats.date_range[1]}"))
    items = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in pairs)
    out = f"<h2>Summary</h2>\n<table>\n{items}\n</table>\n"

    if stats.numeric_stats:
        rows = "".join(
            f"<tr><td>{n.column}</td><td>{n.count}</td><td>{n.min:.2f}</td>"
            f"<td>{n.max:.2f}</td><td>{n.mean:.2f}</td><td>{n.median:.2f}</td></tr>"
            for n in stats.numeric_stats
        )
        out += (
            "<h3>Numeric summary</h3>\n<table>\n"
            "<tr><th>Column</th><th>Count</th><th>Min</th><th>Max</th>"
            "<th>Mean</th><th>Median</th></tr>\n"
            f"{rows}\n</table>\n"
        )
    return out


def _bar_html(rows: list[tuple[str, int | float]], title: str, width: int = 40) -> str:
    if not rows:
        return ""
    max_val = max(v for _, v in rows)
    label_width = max(len(str(k)) for k, _ in rows)
    body = []
    for label, value in rows:
        bar = _ascii_bar(float(value), float(max_val), width=width)
        val_str = f"{value:.2f}" if isinstance(value, float) else str(value)
        body.append(f"{str(label).ljust(label_width)}  {bar}  {val_str}")
    return f"<h3>{title}</h3>\n<pre>{chr(10).join(body)}</pre>\n"


def export_html(
    path: Path,
    schema: SchemaInfo,
    stats: SummaryStats,
    chart_rows: list[tuple[str, list[tuple[str, int | float]]]] | None = None,
    where: str | None = None,
) -> None:
    """Write a self-contained report: preformatted ASCII, minimal CSS, no JavaScript."""
    name = Path(schema.path).name
    parts = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>Data Report: {name}</title>",
        f"<style>{_HTML_CSS}</style></head><body>",
        f"<h1>Data Report: {name}</h1>",
    ]
    # A filtered report looks like a full one once it is saved, so say so.
    if where:
        parts.append(f"<p>Filtered by: <code>{escape(where)}</code></p>")
    parts += [
        _summary_html(stats),
        _schema_html(schema),
    ]
    for title, rows in chart_rows or []:
        parts.append(_bar_html(rows, title))
    parts.append("</body></html>")
    path.write_text("\n".join(parts) + "\n")
