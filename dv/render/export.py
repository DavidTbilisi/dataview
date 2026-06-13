from pathlib import Path

from dv.core.schema import SchemaInfo
from dv.core.stats import SummaryStats


def _ascii_bar(value: float, max_value: float, width: int = 40) -> str:
    if max_value == 0:
        return ""
    return "#" * int(value / max_value * width)


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
) -> None:
    name = Path(schema.path).name
    lines = [f"# Data Report: {name}\n\n"]
    lines.append(_summary_md(stats))
    lines.append(_schema_md(schema))
    lines.append("\n")

    if chart_rows:
        for title, rows in chart_rows:
            lines.append(_bar_md(rows, title))

    path.write_text("".join(lines))
