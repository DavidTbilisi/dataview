Money-specific views are a perfect fit for `dv` because money data is usually:

```text
date + category + account + amount + note
```

That means you can get strong analytics from simple CSV files.

# Recommended money schema

For personal finance, use this base format:

```csv
date,type,category,subcategory,amount,account,method,note
2026-06-01,expense,food,groceries,25.50,cash,cash,vegetables
2026-06-02,income,salary,main,2500.00,bank,transfer,monthly salary
2026-06-03,expense,transport,bus,3.00,cash,cash,bus
2026-06-04,expense,software,subscription,15.00,card,card,tool
```

Important columns:

```text
date          when it happened
type          income / expense / transfer / debt / saving
category      food, rent, study, transport, etc.
subcategory   groceries, restaurant, books, bus, etc.
amount        numeric value
account       cash, bank, card, savings
method        cash, card, transfer
note          free text
```

# 1. Money summary

Command:

```bash
dv money.csv money-summary
```

Output:

```text
MONEY SUMMARY

Period:       2026-06-01 -> 2026-06-30

Income:       2,500.00
Expenses:     1,420.50
Saved:        1,079.50
Savings rate: 43.2%

Transactions: 84
Avg expense:  16.91
Max expense:  350.00
Accounts:     cash, bank, card, savings

Health
------
Cashflow:     POSITIVE
Overspending: WARNING
Missing data: OK
```

This should be the default money dashboard.

---

# 2. Income vs expense

Command:

```bash
dv money.csv income-expense --by month
```

Output:

```text
INCOME VS EXPENSE

Month    Income      Expense     Saved      Savings %
-------  ----------  ----------  ---------  ---------
Jan      2,500.00    1,800.00    700.00     28.0%
Feb      2,500.00    1,620.00    880.00     35.2%
Mar      2,700.00    1,950.00    750.00     27.8%
Apr      2,700.00    1,500.00    1,200.00   44.4%
May      2,700.00    1,740.00    960.00     35.6%
Jun      2,900.00    1,420.50    1,479.50   51.0%
```

Bar version:

```text
MONTHLY CASHFLOW

Jan  income  #########################  2500
     expense ##################         1800

Feb  income  #########################  2500
     expense ################           1620

Mar  income  ########################### 2700
     expense ###################         1950
```

---

# 3. Expenses by category

Command:

```bash
dv money.csv expenses-by category
```

Output:

```text
EXPENSES BY CATEGORY

food        ########################  420.50   29.6%
rent        ####################      350.00   24.6%
study       ########                  140.00    9.9%
software    ######                    110.00    7.7%
transport   ####                       80.00    5.6%
other       ##################        320.00   22.5%

Total: 1,420.50
```

This replaces a pie chart. In ASCII, bars are better.

---

# 4. Category drilldown

Command:

```bash
dv money.csv drill category food
```

Output:

```text
CATEGORY: food

Total: 420.50
Transactions: 18
Average: 23.36

Subcategories
-------------
groceries     ####################  290.00
restaurant    ########              100.50
coffee        ##                     30.00

Largest transactions
--------------------
Date        Amount   Note
----------  -------  ----------------
2026-06-08  85.00    weekly groceries
2026-06-15  70.00    groceries
2026-06-21  45.50    restaurant
```

This is more useful than just showing totals.

---

# 5. Daily spending timeline

Command:

```bash
dv money.csv spend-timeline --by day
```

Output:

```text
DAILY SPENDING: JUNE 2026

01 02 03 04 05 06 07 08 09 10 11 12 13 14 15
## .. #. ## .. .. ## ## #. ## .. #. ## .. ##

16 17 18 19 20 21 22 23 24 25 26 27 28 29 30
## ## .. ## #. .. .. ## ## ## ## .. .. #. ##

Legend:
.. no spending
#. low spending
## high spending
```

Useful for seeing spending frequency.

---

# 6. Spending calendar heatmap

Command:

```bash
dv money.csv calendar --date date --value amount --where "type='expense'"
```

Output:

```text
SPENDING CALENDAR: 2026

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

This quickly shows “danger days.”

---

# 7. Weekday spending pattern

Command:

```bash
dv money.csv spend-by-weekday
```

Output:

```text
SPENDING BY WEEKDAY

Mon   ###########           210.00
Tue   ################      320.00
Wed   ########              160.00
Thu   ############          240.00
Fri   ####################  400.00
Sat   ###############       300.00
Sun   ######                120.00
```

This answers:

```text
Which days cost me most?
```

---

# 8. Hour spending pattern

For card/bank exports with timestamps.

Command:

```bash
dv money.csv spend-by-hour --date timestamp
```

Output:

```text
SPENDING BY HOUR

06  #                     12.00
07  ##                    25.00
08  #####                 60.00
09  ####                  50.00
10  ########              110.00
11  ############          180.00
12  ####################  300.00
13  ###############       230.00
14  #######               100.00
15  #####                 70.00
16  ####                  50.00
17  ########              120.00
18  ###########           170.00
19  ######                90.00
20  ###                   40.00
21  ##                    30.00
```

Useful for impulse-spending detection.

---

# 9. Budget vs actual

Command:

```bash
dv money.csv budget --budget budget.yml
```

Example `budget.yml`:

```yaml
food: 400
rent: 350
transport: 100
software: 80
study: 150
other: 200
```

Output:

```text
BUDGET VS ACTUAL

Category    Budget   Actual   Diff     Used
----------  -------  -------  -------  --------------------
food        400.00   420.50   +20.50   ##################### OVER
rent        350.00   350.00     0.00   #################### OK
transport   100.00    80.00   -20.00   ################ OK
software     80.00   110.00   +30.00   ######################## OVER
study       150.00   140.00   -10.00   ################## OK
other       200.00   320.00  +120.00   ############################ OVER
```

Symbols matter:

```text
OK       within budget
OVER     exceeded budget
WARN     close to limit
```

---

# 10. Burn rate

Command:

```bash
dv money.csv burn-rate --month 2026-06
```

Output:

```text
BURN RATE: JUNE 2026

Month budget:      1,500.00
Spent so far:      820.00
Days passed:       13 / 30
Days left:         17

Daily budget:      50.00
Actual daily avg:  63.08
Projected spend:   1,892.40

Status: OVER PACE

Progress
Budget     [##############################]  1,500.00
Projected  [######################################]  1,892.40
```

This is one of the most useful money views.

---

# 11. Remaining budget countdown

Command:

```bash
dv money.csv remaining --budget 1500 --month 2026-06
```

Output:

```text
REMAINING BUDGET

Budget:        1,500.00
Spent:           820.00
Remaining:       680.00
Days left:        17

Safe daily spend: 40.00

Remaining
[#############-----------------] 45.3%
```

This gives actionable information.

---

# 12. Savings rate

Command:

```bash
dv money.csv savings-rate --by month
```

Output:

```text
SAVINGS RATE

Month    Income    Expense   Saved    Rate
-------  --------  --------  -------  ------
Jan      2500.00   1800.00   700.00   28.0%
Feb      2500.00   1620.00   880.00   35.2%
Mar      2700.00   1950.00   750.00   27.8%
Apr      2700.00   1500.00   1200.00  44.4%
May      2700.00   1740.00   960.00   35.6%
Jun      2900.00   1420.50   1479.50  51.0%

Trend:   .:-=+#
```

This should be a core metric.

---

# 13. Cashflow forecast

Command:

```bash
dv money.csv forecast --months 3
```

Output:

```text
CASHFLOW FORECAST

Based on last 3 months average.

Expected income:   2,766.67
Expected expense:  1,620.17
Expected saved:    1,146.50

Next 3 months
-------------
Month    Income    Expense   Saved
-------  --------  --------  --------
Jul      2766.67   1620.17   1146.50
Aug      2766.67   1620.17   1146.50
Sep      2766.67   1620.17   1146.50
```

Keep this simple. Do not pretend it is “AI prediction.” It is just a rolling average forecast.

---

# 14. Subscriptions view

Command:

```bash
dv money.csv subscriptions
```

Output:

```text
SUBSCRIPTIONS

Monthly recurring:
------------------
Service       Amount   Last paid    Est yearly
------------  -------  -----------  ----------
Netflix       12.99    2026-06-04   155.88
Hosting       8.00     2026-06-10   96.00
Tool          15.00    2026-06-05   180.00

Monthly total: 35.99
Yearly total:  431.88
```

Detection rule:

```text
same merchant/note + similar amount + repeated monthly
```

This is high value.

---

# 15. Recurring expenses

Command:

```bash
dv money.csv recurring
```

Output:

```text
RECURRING EXPENSES

Name          Frequency   Amount   Confidence
------------  ----------  -------  ----------
Rent          monthly     350.00   high
Hosting       monthly     8.00     high
Phone         monthly     20.00    medium
Transport     weekly      12.00    medium
```

This helps separate fixed vs variable spending.

---

# 16. Fixed vs variable expenses

Command:

```bash
dv money.csv fixed-variable
```

Output:

```text
FIXED VS VARIABLE

Fixed expenses:     520.00   ################
Variable expenses:  900.50   ###########################

Total:              1,420.50

Fixed categories
----------------
rent        350.00
internet     40.00
phone        20.00
software    110.00
```

This is important for financial control.

---

# 17. Largest transactions

Command:

```bash
dv money.csv largest --limit 10
```

Output:

```text
LARGEST TRANSACTIONS

Date        Type      Category    Amount    Note
----------  --------  ----------  --------  ----------------
2026-06-01  expense   rent        350.00    rent
2026-06-08  expense   food        85.00     weekly groceries
2026-06-15  expense   study       70.00     course
2026-06-22  expense   software    50.00     license
```

Simple but essential.

---

# 18. Outlier transactions

Command:

```bash
dv money.csv outliers amount
```

Output:

```text
OUTLIER TRANSACTIONS

Rule: amount > Q3 + 1.5 * IQR

Date        Category    Amount    Note
----------  ----------  --------  ----------------
2026-06-01  rent        350.00    rent
2026-06-15  study       210.00    course
2026-06-22  software    180.00    annual license
```

Useful for finding unusual spending.

---

# 19. Merchant / note analysis

Command:

```bash
dv money.csv merchants --from note
```

Output:

```text
MERCHANT ANALYSIS

Merchant      Count   Total    Avg
------------  ------  -------  ------
Carrefour     12      310.50   25.88
Bolt          8       95.00    11.88
Amazon        4       240.00   60.00
Pharmacy      3       42.00    14.00
```

This needs fuzzy cleanup later, but even basic grouping helps.

---

# 20. Account balances

For snapshot data:

```csv
date,account,balance
2026-06-01,cash,120
2026-06-01,bank,2400
2026-06-01,savings,5000
```

Command:

```bash
dv balances.csv balances
```

Output:

```text
ACCOUNT BALANCES

Date: 2026-06-13

cash       120.00
bank       2,400.00
savings    5,000.00
----------------
total      7,520.00
```

Trend:

```text
NET WORTH TREND

Jan  6,200  ######
Feb  6,800  #######
Mar  7,100  ########
Apr  7,000  #######
May  7,350  ########
Jun  7,520  #########
```

---

# 21. Debt tracker

Command:

```bash
dv debt.csv debt
```

Schema:

```csv
date,name,balance,payment,interest_rate
2026-06-01,loan,5000,300,8.5
```

Output:

```text
DEBT SUMMARY

Total debt:       5,000.00
Monthly payment:    300.00
Interest rate:        8.5%

Progress
Original:  7,000.00
Current:   5,000.00
Paid:      2,000.00

[########------------] 28.6% paid
```

For minors, keep this as tracking/education; no credit product recommendations.

---

# 22. Goal tracker

Command:

```bash
dv goals.csv goals
```

Schema:

```csv
goal,target,current,deadline
Emergency fund,5000,2200,2026-12-31
Laptop,1500,800,2026-09-01
```

Output:

```text
MONEY GOALS

Goal             Current   Target    Progress              Deadline
---------------  --------  --------  --------------------  ----------
Emergency fund   2200      5000      #########-----------  44.0%
Laptop           800       1500      ###########---------  53.3%
```

This is very useful.

---

# 23. Envelope budget

Command:

```bash
dv money.csv envelopes --budget budget.yml
```

Output:

```text
ENVELOPES

food        420.50 / 400.00   OVER   [#####################]
transport    80.00 / 100.00   OK     [################----]
study       140.00 / 150.00   WARN   [##################--]
software    110.00 / 80.00    OVER   [########################]
```

This is the terminal version of envelope budgeting.

---

# 24. Money report

Command:

```bash
dv money.csv money-report --month 2026-06
```

Output:

```text
MONEY REPORT: JUNE 2026

SUMMARY
-------
Income:        2,900.00
Expenses:      1,420.50
Saved:         1,479.50
Savings rate:  51.0%

EXPENSES BY CATEGORY
--------------------
food        ########################  420.50
rent        ####################      350.00
study       ########                  140.00
software    ######                    110.00
transport   ####                       80.00

BUDGET STATUS
-------------
food        OVER   +20.50
software    OVER   +30.00
study       OK     -10.00

LARGEST TRANSACTIONS
--------------------
2026-06-01  rent       350.00
2026-06-08  food        85.00
2026-06-15  study       70.00

CASHFLOW
--------
Income   #############################  2,900.00
Expense  ##############                 1,420.50
Saved    ###############                1,479.50
```

This should become the main money command.

---

# Best money commands for `dv`

```bash
dv money.csv money-summary
dv money.csv money-report --month 2026-06
dv money.csv expenses-by category
dv money.csv income-expense --by month
dv money.csv budget --budget budget.yml
dv money.csv burn-rate --month 2026-06
dv money.csv remaining --budget 1500 --month 2026-06
dv money.csv savings-rate --by month
dv money.csv subscriptions
dv money.csv recurring
dv money.csv fixed-variable
dv money.csv largest --limit 10
dv money.csv outliers amount
dv money.csv goals
dv money.csv envelopes --budget budget.yml
```

# Best build order

```text
1. money-summary
2. expenses-by category
3. income-expense --by month
4. largest
5. budget vs actual
6. burn-rate
7. savings-rate
8. recurring/subscriptions
9. calendar heatmap
10. money-report
```

# Rule for money views

Do not make the tool “smart” too early.

First version should be:

```text
totals
categories
periods
budgets
largest transactions
cashflow
```

Later:

```text
recurring detection
merchant cleanup
forecasting
goal tracking
account balances
```

The highest-value money view is:

```bash
dv money.csv money-report --month current
```

That gives a full monthly finance picture in one terminal command.
