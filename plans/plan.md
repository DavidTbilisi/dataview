These are the **best ASCII views** I would implement for `dv`. Each one maps to a reusable data pattern.

# 1. Summary dashboard

Command:

```bash
dv expenses.csv summary
```

Output:

```text
DATA SUMMARY: expenses.csv

Rows:        1,248
Columns:     6
File type:   CSV
Date range:  2026-01-01 -> 2026-06-30
Missing:     42 cells
Duplicates:  3 rows

Column Types
------------ 
date        date
category    text
amount      number
method      text
note        text
month       date_part

Quick Stats
-----------
Total amount:     12,840.50
Average amount:   10.29
Max amount:        850.00
Min amount:        1.00
```

This should be the **default intelligence view**.

---

# 2. Schema view

Command:

```bash
dv expenses.csv schema
```

Output:

```text
SCHEMA

Column      Type      Missing   Missing %   Unique   Example
----------  --------  --------  ----------  -------  ----------------
date        date      0         0.0%        180      2026-06-01
category    text      4         0.3%        12       food
amount      number    0         0.0%        910      25.50
method      text      0         0.0%        4        card
note        text      321       25.7%       800      groceries
```

This is essential for unknown files.

---

# 3. Clean table view

Command:

```bash
dv expenses.csv table --limit 10
```

Output:

```text
EXPENSES

#   Date        Category    Amount   Method   Note
--  ----------  ----------  -------  -------  ----------------
1   2026-06-01  food        25.50    cash     groceries
2   2026-06-02  study       12.00    card     book
3   2026-06-03  transport   3.00     cash     bus
4   2026-06-04  food        9.80     card     lunch
5   2026-06-05  software    15.00    card     subscription
```

Add truncation:

```text
long text becomes this...
```

---

# 4. Bar chart

Command:

```bash
dv expenses.csv bar category --sum amount
```

Output:

```text
AMOUNT BY CATEGORY

food        ########################  4,520.50
rent        ####################      3,800.00
study       #######                   1,240.00
software    #####                       890.00
transport   ###                         420.00
other        ##                          260.00
```

This is the most useful ASCII chart.

---

# 5. Horizontal ranking

Command:

```bash
dv expenses.csv top category --by amount
```

Output:

```text
TOP CATEGORIES BY AMOUNT

Rank  Category     Amount     Share
----  -----------  ---------  ------
1     food         4,520.50   35.2%
2     rent         3,800.00   29.6%
3     study        1,240.00   9.7%
4     software       890.00   6.9%
5     transport      420.00   3.3%
```

Better than a bar chart when exact ranking matters.

---

# 6. Histogram

Command:

```bash
dv expenses.csv hist amount
```

Output:

```text
AMOUNT DISTRIBUTION

Range       Count   Chart
----------  ------  --------------------
0-10        530     ####################
10-25       310     ############
25-50       180     #######
50-100      90      ###
100-250     45      ##
250-500     12      #
500+        3       #
```

Good for durations, prices, scores, file sizes, salaries, sleep time, etc.

---

# 7. Sparkline

Command:

```bash
dv expenses.csv spark amount --by date
```

ASCII-safe:

```text
AMOUNT OVER TIME

2026-01  2026-02  2026-03  2026-04  2026-05  2026-06
.:-=+*#%%#*+=-:.:-=+*#
```

Unicode mode:

```text
AMOUNT OVER TIME

Jan Feb Mar Apr May Jun
▁▂▃▅▆█▇▆▄▃▂▁▂▃▆█
```

Sparklines are excellent for compact dashboards.

---

# 8. Calendar heatmap

Command:

```bash
dv study.csv calendar --date date --value minutes
```

Output:

```text
STUDY ACTIVITY: 2026

        Jan       Feb       Mar       Apr       May       Jun
Mon     .++*#     .+**#     +++##     ..+*#     +**##     ++###
Tue     ++*##     .++*#     ++###     .+**#     ++*##     +####
Wed     .+**#     ++###     .+**#     ++###     .++*#     ++###
Thu     ++###     .++*#     ++###     +++##     .+**#     +**##
Fri     .++*#     ++###     .++*#     .+**#     ++###     .++*#
Sat     ..++*     ..+**     ...++     ..++*     ..+**     ...++
Sun     ...+.     ....+     ....+     ...+.     ...++     ....+

Legend: . none   + low   * medium   # high
```

Useful for:

```text
study
habits
coding
sleep
fitness
reading
work logs
```

---

# 9. Matrix heatmap

Command:

```bash
dv logs.csv heatmap weekday hour --count
```

Output:

```text
EVENTS BY WEEKDAY / HOUR

       00 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17
Mon    .  .  .  .  .  +  *  #  #  #  *  +  +  *  #  #  *  +
Tue    .  .  .  .  +  +  *  #  #  *  *  +  +  *  #  #  #  *
Wed    .  .  .  .  .  +  +  *  #  #  *  +  +  *  #  #  *  +
Thu    .  .  .  +  +  *  #  #  #  *  +  +  *  #  #  *  +  .
Fri    .  .  .  .  +  *  #  #  *  +  +  *  #  #  *  +  .  .
Sat    .  .  .  .  .  .  +  +  *  *  +  +  .  .  .  .  .  .
Sun    .  .  .  .  .  .  .  +  +  *  +  .  .  .  .  .  .  .

Legend: . 0   + low   * medium   # high
```

Great for logs and behavior patterns.

---

# 10. Timeline view

Command:

```bash
dv tasks.csv timeline --start start --end end --label task
```

Output:

```text
TIMELINE

Range: 2026-06-01 -> 2026-06-30

          01        10        20        30
          |---------|---------|---------|

Parser    [###]
Renderer        [#####]
Importer              [####]
Testing                    [######]
Release                            *
```

This becomes the reusable base for Gantt charts.

---

# 11. Gantt view

Command:

```bash
dv tasks.csv gantt --start start --end end --label task --status status
```

Output:

```text
GANTT

Range: 2026-06-01 -> 2026-06-30

ID  Status   Task              Start       End         Timeline
--  -------  ----------------  ----------  ----------  ------------------------------
1   done     Parser            2026-06-01  2026-06-03  [###]
2   active   Renderer          2026-06-05  2026-06-09       [##---]
3   todo     Importer          2026-06-10  2026-06-12            [===]
4   blocked  Testing           2026-06-15  2026-06-20                 [xxxxxx]
5   mile     Release           2026-06-30  2026-06-30                              *
```

Legend:

```text
[###] done
[##-] active / partial
[===] planned
[xxx] blocked
*     milestone
```

---

# 12. Tree view

Command:

```bash
dv expenses.csv tree --path category/subcategory/item
```

Output:

```text
EXPENSE TREE

Expenses
|-- Food
|   |-- Groceries
|   |   |-- vegetables
|   |   `-- bread
|   `-- Restaurant
|       |-- lunch
|       `-- coffee
|-- Study
|   |-- Books
|   `-- Courses
`-- Software
    |-- Hosting
    `-- Subscriptions
```

Useful for:

```text
categories
folders
projects
knowledge maps
book outlines
Bible study topics
```

---

# 13. Pivot table

Command:

```bash
dv expenses.csv pivot category month --sum amount
```

Output:

```text
AMOUNT BY CATEGORY / MONTH

Category     Jan     Feb     Mar     Apr     May     Jun     Total
----------  ------  ------  ------  ------  ------  ------  -------
food        620.00  590.00  710.00  680.00  750.00  800.50  4150.50
study       80.00   120.00  90.00   300.00  200.00  450.00  1240.00
software    50.00   70.00   200.00  150.00  180.00  240.00  890.00
transport   60.00   55.00   70.00   80.00   75.00   80.00   420.00
```

This is one of the strongest analytics views.

---

# 14. Correlation / scatter approximation

Command:

```bash
dv data.csv scatter study_hours score
```

Output:

```text
SCATTER: study_hours vs score

score
100 |                         *
 90 |                    *  *   *
 80 |              *   *  *
 70 |          *  *
 60 |      * *
 50 |   *
    +------------------------------
      0    2    4    6    8    10

study_hours
```

Useful when both fields are numeric.

---

# 15. Box summary

Command:

```bash
dv scores.csv box score
```

Output:

```text
SCORE DISTRIBUTION

min       q1       median       q3       max
45        62       74           88       100

45        62       74           88       100
|---------|========|============|---------|
          q1       median       q3
```

Good for scores, prices, task duration, sleep hours.

---

# 16. Diff view

Command:

```bash
dv current.csv diff previous.csv --key id
```

Output:

```text
DIFF: previous.csv -> current.csv

Added:      3
Removed:    1
Changed:    4

Changed rows
------------
ID   Field      Previous       Current
---  ---------  -------------  -------------
12   status     todo           done
18   amount     25.00          30.00
21   category   food           study

Added rows
----------
+ 31  software  15.00  subscription
+ 32  food      8.50   lunch

Removed rows
------------
- 7   transport 3.00 bus
```

Very useful for comparing exports.

---

# 17. Missing values view

Command:

```bash
dv file.csv missing
```

Output:

```text
MISSING VALUES

Column      Missing   Percent   Chart
----------  --------  --------  --------------------
note        321       25.7%     ##########
category    4         0.3%      #
amount      0         0.0%
date        0         0.0%
method      0         0.0%
```

This should exist in version 1.

---

# 18. Outlier view

Command:

```bash
dv expenses.csv outliers amount
```

Output:

```text
OUTLIERS: amount

Rule: values above q3 + 1.5 * IQR

Date        Category    Amount   Note
----------  ----------  -------  ----------------
2026-02-14  software    850.00   annual license
2026-04-02  study       420.00   course
2026-05-10  travel      390.00   flight
```

Good for finance, logs, scores, durations.

---

# 19. Composition view

Command:

```bash
dv expenses.csv composition category --sum amount
```

Output:

```text
COMPOSITION: amount by category

food        35.2%  ##################
rent        29.6%  ###############
study        9.7%  #####
software     6.9%  ###
transport    3.3%  ##
other        15.3%  ########

Total: 12,840.50
```

This replaces pie charts in ASCII.

---

# 20. Full report view

Command:

```bash
dv expenses.csv report
```

Output:

```text
REPORT: expenses.csv

SUMMARY
-------
Rows:        1,248
Columns:     6
Date range:  2026-01-01 -> 2026-06-30
Total:       12,840.50

SCHEMA
------
date        date      missing: 0
category    text      missing: 4
amount      number    missing: 0
method      text      missing: 0
note        text      missing: 321

TOP CATEGORIES
--------------
food        ########################  4,520.50
rent        ####################      3,800.00
study       #######                   1,240.00

AMOUNT HISTOGRAM
----------------
0-10        ####################  530
10-25       ############          310
25-50       #######               180
50-100      ###                   90
100+        ##                    60

MISSING VALUES
--------------
note        ##########  321
category    #           4
```

This is the “one command to understand the file” view.

---

# Views I would implement first

```text
1. summary
2. schema
3. table
4. group-by table
5. bar chart
6. histogram
7. timeline
8. heatmap
9. pivot table
10. report
```

That gives you the highest payoff. Everything else can come later.
