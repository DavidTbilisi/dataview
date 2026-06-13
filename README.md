# dv - Personal Terminal DataView

Local-first CLI for inspecting, querying, and visualizing structured data in a terminal.
Powered by DuckDB, rendered with Rich.

```
any file -> summary / query / chart / report
```

No web server. No frontend. Just files and terminal output.

## Install

Requires Python 3.11+ and [uv](https://github.com/astral-sh/uv).

```bash
git clone <repo>
cd dataview
uv sync
uv pip install -e .
```

Run with either:

```bash
uv run dv --help
dv --help
```

## CLI shape

```bash
dv <file> <command> [options]
```

Input files are registered in DuckDB as table `data`, so SQL commands can target that name directly.

## Quick start

```bash
dv examples/expenses.csv schema
dv examples/expenses.csv summary
dv examples/expenses.csv query "SELECT category, sum(amount) AS total FROM data GROUP BY category ORDER BY total DESC"
dv examples/expenses.csv bar category
dv examples/tasks.csv timeline --start start --end end --label task
```

## Commands

### Inspect and query

- `schema`
- `head`
- `summary`
- `describe`
- `missing`
- `table`
- `query`
- `report`

Examples:

```bash
dv examples/expenses.csv schema
dv examples/expenses.csv head -n 5
dv examples/expenses.csv table --where "amount > 30" --sort amount --desc
dv examples/expenses.csv query "SELECT * FROM data LIMIT 20"
```

### Aggregation

- `group-by`
- `pivot`
- `top`

Examples:

```bash
dv examples/expenses.csv group-by category --sum amount
dv examples/expenses.csv group-by category --count --bar
dv examples/expenses.csv pivot category date --sum amount
dv examples/expenses.csv top category --by amount
```

### Charts and visuals

- `bar`
- `hist`
- `spark`
- `scatter`
- `composition`
- `box`
- `outliers`
- `heatmap`
- `timeline`
- `gantt`
- `tree`
- `calendar`

Examples:

```bash
dv examples/expenses.csv bar category
dv examples/expenses.csv hist amount --bins 12
dv examples/expenses.csv spark amount --by date
dv examples/tasks.csv gantt --start start --end end --label task --status status --progress progress
dv examples/books.csv tree --path genre/subgenre/title
```

### Time analysis

- `time-summary`
- `time`
- `by-hour`
- `streak`
- `gaps`
- `compare-periods`

Examples:

```bash
dv examples/expenses.csv time-summary --date date
dv examples/expenses.csv time --date date --by month --sum amount
dv examples/expenses.csv by-hour --date date
dv examples/expenses.csv compare-periods --date date --value amount --period month
```

### Compare and export

- `diff`
- `export-md`

Examples:

```bash
dv examples/expenses.csv diff examples/study.csv --key date
dv examples/expenses.csv export-md report.md
```

## Screenshots

![schema](docs/screenshots/schema.svg)
![summary](docs/screenshots/summary.svg)
![head](docs/screenshots/head.svg)
![query](docs/screenshots/query.svg)
![group-by](docs/screenshots/groupby.svg)
![bar](docs/screenshots/bar.svg)
![hist](docs/screenshots/hist.svg)
![timeline](docs/screenshots/timeline.svg)

## Supported formats

| Extension | Format |
|-----------|--------|
| `.csv` | CSV |
| `.tsv` | TSV |
| `.json` | JSON |
| `.jsonl` / `.ndjson` | Newline-delimited JSON |
| `.parquet` | Parquet |
| `.sqlite` / `.db` | SQLite |
| `.duckdb` | DuckDB |

## Config

Optional `.dv.yml` in the project directory or `~/.dv.yml`:

```yaml
default_limit: 50
date_format: "%Y-%m-%d"
charts:
  width: 60
aliases:
  money:
    group_by: category
    sum: amount
```

## Development

Run tests:

```bash
uv run pytest
```

Project layout:

```text
dv/
  main.py           CLI commands (Typer)
  core/             Detection, query, schema, stats, config
  render/           Terminal tables and chart renderers
  tui/              Reserved for later interactive mode
examples/           Sample datasets
tests/              Unit tests
```

## Stack

- [Typer](https://typer.tiangolo.com/) - CLI framework
- [Rich](https://github.com/Textualize/rich) - terminal rendering
- [DuckDB](https://duckdb.org/) - analytics query engine
- [Pandas](https://pandas.pydata.org/) - normalization helpers
- [uv](https://github.com/astral-sh/uv) - environment and package management
