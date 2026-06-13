Use this as the build brief for Claude Code. It is intentionally scoped as a **personal CLI/TUI analytics tool**, not a web dashboard.

# Build Plan: `dv` — Personal ASCII DataView CLI/TUI

## Goal

Build a local-first command-line app called `dv` that can inspect, summarize, query, and visualize many kinds of structured data using fast ASCII/terminal output.

The app should be cheap to maintain, fast to run, and useful for personal analytics.

Primary goal:

```text
any file/table -> summary/query/chart/report
```

Do not build a web app. Do not over-engineer. Prioritize useful output.

---

## Recommended stack

Use Python first for speed of development.

```text
Python 3.11+
Typer       CLI framework
Rich        terminal tables, panels, layouts
DuckDB      analytics/query engine
Pandas      optional data normalization
Textual     later TUI mode
PyYAML      config support
```

Use this `pyproject.toml` dependency set:

```toml
[project]
name = "dv"
version = "0.1.0"
description = "Personal terminal dataview tool"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.12",
    "rich>=13.7",
    "duckdb>=1.0",
    "pandas>=2.2",
    "pyarrow>=16.0",
    "textual>=0.70",
    "pyyaml>=6.0"
]

[project.scripts]
dv = "dv.main:app"
```

---

# Core idea

`dv` should treat every input as a table when possible.

Supported inputs:

```text
CSV
TSV
JSON
NDJSON / JSONL
Parquet
SQLite
DuckDB
plain text logs later
```

Internal flow:

```text
input file
  -> detect format
  -> infer schema
  -> register table in DuckDB as "data"
  -> run query/aggregation
  -> render table/chart/report
```

The main abstraction should be:

```python
class DataSource:
    path: Path
    format: str
    table_name: str = "data"
```

And:

```python
class ResultView:
    columns: list[str]
    rows: list[dict]
    metadata: dict
```

---

# CLI commands

Implement these commands first:

```bash
dv file.csv summary
dv file.csv schema
dv file.csv head
dv file.csv table
dv file.csv query "select * from data limit 20"
dv file.csv group-by status --count
dv file.csv group-by category --sum amount
dv file.csv bar status
dv file.csv hist duration
dv file.csv top category --by amount
dv file.csv missing
dv file.csv export-md report.md
```

Use command structure:

```bash
dv <input> <command> [options]
```

Examples:

```bash
dv expenses.csv summary
dv expenses.csv group-by category --sum amount
dv tasks.json bar status
dv logs.csv query "select level, count(*) from data group by level"
```

---

# Project structure

Create this structure:

```text
dv/
  __init__.py
  main.py

  core/
    __init__.py
    datasource.py
    detect.py
    schema.py
    query.py
    stats.py
    config.py

  render/
    __init__.py
    table.py
    summary.py
    charts.py
    histogram.py
    heatmap.py
    timeline.py
    tree.py
    export.py

  tui/
    __init__.py
    app.py

tests/
  test_detect.py
  test_schema.py
  test_query.py
  test_charts.py

examples/
  expenses.csv
  tasks.csv
  books.csv
  study.csv
```

---

# Phase 1: File loading and schema detection

Implement format detection:

```text
.csv     CSV
.tsv     TSV
.json    JSON
.jsonl   NDJSON
.ndjson  NDJSON
.parquet Parquet
.sqlite  SQLite
.db      SQLite
.duckdb  DuckDB
```

Commands:

```bash
dv file.csv schema
dv file.csv head
dv file.csv summary
```

Expected schema output:

```text
SCHEMA: expenses.csv

Rows: 1248
Columns: 5

Column      Type      Missing   Unique
----------  --------  --------  ------
date        date      0         180
category    text      4         12
amount      number    0         910
method      text      0         4
note        text      321       800
```

Type inference:

```text
integer
float
number
text
date
datetime
boolean
unknown
```

Use DuckDB for actual data reading where possible.

---

# Phase 2: Query engine

Every file should be registered as a DuckDB table named `data`.

Implement:

```bash
dv file.csv query "select * from data limit 10"
```

Also support:

```bash
dv file.csv table --limit 50
dv file.csv table --columns date,category,amount
dv file.csv table --where "amount > 100"
dv file.csv table --sort amount
dv file.csv table --desc
```

Important: keep raw SQL available. This gives the tool high power without writing every possible feature manually.

---

# Phase 3: Summary analytics

Implement:

```bash
dv file.csv summary
dv file.csv missing
dv file.csv describe
```

`summary` should show:

```text
file name
file type
row count
column count
numeric columns
text columns
date columns
missing value count
duplicate row count
memory estimate
```

`describe` should show for numeric columns:

```text
count
min
max
mean
median
std
```

Example:

```text
NUMERIC SUMMARY

Column     Count   Min    Max     Mean    Median
---------  ------  -----  ------  ------  ------
amount     1248    1.20   850.00  42.80   19.99
duration   400     1      120     14.50   8
```

---

# Phase 4: ASCII visualizations

Implement ASCII-safe renderers first. Unicode can be optional with `--unicode`.

## 1. Bar chart

Command:

```bash
dv file.csv bar status
```

Output:

```text
status

done       ##########  10
active     ####        4
blocked    ##          2
todo       #######     7
```

Options:

```bash
--limit 20
--sort count
--width 60
--unicode
```

## 2. Histogram

Command:

```bash
dv file.csv hist amount
```

Output:

```text
amount histogram

0-10        ###########  53
10-50       ####################  101
50-100      #######  34
100-500     ###  14
500+        #  2
```

Options:

```bash
--bins 10
--width 60
```

## 3. Sparkline

Command:

```bash
dv file.csv spark amount --by date
```

ASCII output:

```text
amount by date
.:-=+*#%%#*+=-:
```

Unicode option:

```text
▁▂▃▅▆█▇▆▄▃▂
```

## 4. Heatmap

Command:

```bash
dv file.csv heatmap weekday hour --count
```

Output:

```text
        00 01 02 03 04 05 06 07 08 09
Mon     .  .  .  +  +  *  #  #  *  +
Tue     .  .  +  +  *  #  #  #  *  +
Wed     .  .  .  +  +  *  #  *  +  .
```

Legend:

```text
. none   + low   * medium   # high
```

## 5. Timeline

For data with start/end/date fields.

Command:

```bash
dv tasks.csv timeline --start start --end end --label task
```

Output:

```text
Timeline

Parser          [###]
Renderer              [#####]
Importer                    [####]
Release                            *
```

## 6. Tree

For hierarchical data.

Command:

```bash
dv file.csv tree --path category/subcategory/name
```

Output:

```text
Root
|-- Food
|   |-- Groceries
|   `-- Restaurant
|-- Study
|   |-- Math
|   `-- Programming
```

---

# Phase 5: Grouping and aggregation

Implement:

```bash
dv file.csv group-by status --count
dv file.csv group-by category --sum amount
dv file.csv group-by month --sum amount
dv file.csv group-by category --avg amount
dv file.csv top category --by amount
```

Generated SQL examples:

```sql
select status, count(*) as count
from data
group by status
order by count desc;
```

```sql
select category, sum(amount) as total
from data
group by category
order by total desc;
```

Output as a table and optionally chart:

```bash
dv expenses.csv group-by category --sum amount --bar
```

---

# Phase 6: Markdown and HTML export

Implement:

```bash
dv file.csv export-md report.md
dv file.csv export-html report.html
```

Markdown report should include:

```text
title
summary
schema
missing values
numeric summary
selected charts as code blocks
```

Example:

````markdown
# Data Report: expenses.csv

## Summary

Rows: 1248
Columns: 5

## Schema

...

## Category Totals

```text
food       ##########  450.20
study      ####        120.00
````

````

HTML export can be simple:

```text
preformatted ASCII inside <pre>
minimal CSS
no JavaScript
````

---

# Phase 7: Config files

Support optional `.dv.yml`.

Example:

```yaml
default_limit: 50
unicode: false
date_format: "%Y-%m-%d"
charts:
  width: 60
aliases:
  money:
    group_by: category
    sum: amount
```

Then:

```bash
dv expenses.csv alias money
```

Can execute predefined views later.

---

# Phase 8: TUI mode

Add later:

```bash
dv file.csv tui
```

TUI screens:

```text
1. Summary
2. Table browser
3. Query input
4. Chart selector
5. Schema view
```

Keyboard:

```text
q       quit
tab     next panel
/       search
s       sort
f       filter
g       group
c       chart
:       SQL command
```

Do not build TUI before CLI is useful.

---

# Acceptance criteria

The app is successful when these commands work:

```bash
dv examples/expenses.csv summary
dv examples/expenses.csv schema
dv examples/expenses.csv head
dv examples/expenses.csv query "select category, sum(amount) total from data group by category order by total desc"
dv examples/expenses.csv group-by category --sum amount
dv examples/expenses.csv bar category
dv examples/expenses.csv hist amount
dv examples/tasks.csv timeline --start start --end end --label task
dv examples/expenses.csv export-md report.md
```

All output should be readable in a plain terminal.

---

# Design constraints

Follow these constraints:

```text
1. No web server.
2. No frontend.
3. No auth.
4. No database server.
5. Use local files.
6. Use DuckDB for analytics.
7. Keep rendering separate from analytics.
8. Keep CLI usable before TUI.
9. Prefer useful output over perfect architecture.
10. Add tests for detection, queries, and chart rendering.
```

---

# Implementation order

Build in this order:

```text
1. Project skeleton
2. CLI app with Typer
3. File detection
4. DuckDB registration
5. schema command
6. head command
7. query command
8. summary command
9. table renderer
10. bar chart renderer
11. histogram renderer
12. group-by command
13. export-md
14. timeline renderer
15. heatmap renderer
16. config file
17. TUI mode
```

Do not skip to TUI early.

---

# Example data files

Create `examples/expenses.csv`:

```csv
date,category,amount,method,note
2026-06-01,food,25.50,cash,groceries
2026-06-02,study,12.00,card,book
2026-06-03,transport,3.00,cash,bus
2026-06-04,food,9.80,card,lunch
2026-06-05,software,15.00,card,subscription
```

Create `examples/tasks.csv`:

```csv
task,start,end,status,progress
Build parser,2026-06-01,2026-06-03,done,100
Render chart,2026-06-05,2026-06-09,active,40
Import CSV,2026-06-10,2026-06-12,todo,0
Release,2026-06-20,2026-06-20,milestone,0
```

---

# Quality target

The app should feel like this:

```text
small
fast
local
boring
powerful
scriptable
ASCII-first
```

The first version should not try to visualize literally everything. It should support the most reusable representations:

```text
table
summary
schema
bar chart
histogram
sparkline
heatmap
timeline
tree
markdown report
SQL query
```

That covers most personal data problems.

## Important correction

“Visualize any information possible” is too broad. The practical version is:

```text
visualize any information that can be converted into:
- rows
- columns
- dates
- categories
- numbers
- hierarchy
- events
```

That is still a huge range:

```text
expenses
study logs
books
projects
tasks
sleep
fitness
server logs
CSV exports
JSON APIs
Bible study notes
reading progress
habit tracking
```

## Strong build order

Do **not** start with TUI.

Build:

```text
1. dv file.csv schema
2. dv file.csv query "select ..."
3. dv file.csv summary
4. dv file.csv bar category
5. dv file.csv hist amount
6. dv file.csv export-md report.md
7. dv file.csv tui
```

The SQL layer is the multiplier. Once DuckDB works, most analytics become one query plus one renderer.
