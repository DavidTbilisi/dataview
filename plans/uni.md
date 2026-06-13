University-specific views are a strong fit for `dv` because university data usually becomes:

```text
course + semester + credits + grade + status + deadline + exam + topic
```

You want views for:

```text
grades
semesters
credits
assignments
exams
syllabus
attendance
GPA
degree progress
study time
prerequisites
```

# Recommended university schema

Use one main file:

```csv
semester,course,credits,status,grade,score,lecturer,exam_date,notes
2026 Spring,Algorithms,6,doing,,0,Dr Smith,2026-06-20,midterm soon
2026 Spring,Databases,6,done,A,96,Dr Brown,2026-06-18,
2026 Spring,Networks,6,failed,F,41,Dr Green,2026-06-25,retake needed
```

Useful columns:

```text
semester      2026 Spring
course        Algorithms
credits       6
status        todo / doing / done / failed / retake
grade         A / B / C / D / F
score         numeric score
lecturer      lecturer name
exam_date     final/midterm date
notes         free text
```

# 1. University dashboard

Command:

```bash
dv university.csv uni-summary
```

Output:

```text
UNIVERSITY SUMMARY

Current semester: 2026 Spring

Courses:        6
Credits:        36
Completed:      3
In progress:    2
Failed/retake:  1

Average score:  86.8
GPA estimate:   3.42 / 4.00

Status
------
done        ############  3
doing       ########      2
failed      ####          1

Risk
----
Algorithms       exam soon
Networks         failed / retake needed
Operating Sys    missing assignment
```

This should be the default university view.

---

# 2. Semester progress

Command:

```bash
dv university.csv semester --current
```

Output:

```text
SEMESTER PROGRESS: 2026 Spring

Course             Credits   Status    Score   Progress
-----------------  --------  --------  ------  --------------------
Algorithms         6         doing     0       ######--------------
Databases          6         done      96      ####################
Networks           6         failed    41      ########------------
Operating Systems  6         doing     88      #################---
Cloud Computing    6         done      92      ####################
Security           6         done      94      ####################

Credits completed: 18 / 36
Progress:          50.0%
```

Good for answering:

```text
Where am I this semester?
What is incomplete?
What should I focus on?
```

---

# 3. GPA / grade view

Command:

```bash
dv university.csv grades
```

Output:

```text
GRADES

Course             Credits   Score   Grade   Weighted Points
-----------------  --------  ------  ------  ---------------
Databases          6         96      A       24.0
Cloud Computing    6         92      A       24.0
Security           6         94      A       24.0
Operating Systems  6         88      B+      21.0
Networks           6         41      F       0.0

GPA estimate: 3.10 / 4.00
Average:      82.2
```

Also useful:

```text
GRADE DISTRIBUTION

A      ############  3
B+     ####          1
B      0
C      0
D      0
F      ####          1
```

---

# 4. Credit completion map

Command:

```bash
dv university.csv credits
```

Output:

```text
DEGREE CREDITS

Required:   240
Completed:  126
Current:     36
Remaining:   78

Progress
[##########----------] 52.5%

By Status
completed    ############################  126
current      ########                      36
remaining    #################             78
```

For degree planning, this is one of the most important views.

---

# 5. Semester-by-semester map

Command:

```bash
dv university.csv roadmap
```

Output:

```text
DEGREE ROADMAP

Semester       Credits   Done   Failed   GPA
-------------  --------  -----  -------  ----
2024 Fall      30        30     0        3.60
2025 Spring    30        24     6        3.20
2025 Fall      36        36     0        3.70
2026 Spring    36        18     6        active

Timeline
2024F   [######]
2025S   [#####x]
2025F   [#######]
2026S   [###---x]
```

Legend:

```text
# completed credits
- in progress
x failed/retake credits
```

---

# 6. Course risk view

Command:

```bash
dv university.csv risk`
```

Output:

```text
COURSE RISK

Course             Risk     Reason
-----------------  -------  ------------------------------
Networks           HIGH     failed score: 41
Algorithms         MEDIUM   exam in 7 days, no score yet
Operating Systems  MEDIUM   missing assignment
Databases          LOW      completed with 96
Security           LOW      completed with 94

Risk Summary
HIGH      ####        1
MEDIUM    ########    2
LOW       ########    2
```

Risk rules:

```text
failed grade          high
score < 60            high
exam within 7 days    medium/high
missing assignment    medium
low attendance        medium/high
```

---

# 7. Assignment deadline view

Command:

```bash
dv assignments.csv deadlines
```

Schema:

```csv
course,title,type,due_date,status,weight
Algorithms,Graph homework,assignment,2026-06-15,todo,10
Databases,Final project,project,2026-06-20,doing,30
Networks,Retake exam,exam,2026-06-25,todo,100
```

Output:

```text
DEADLINES

Title              Course       Type        Due          Left      Status
-----------------  -----------  ----------  -----------  --------  ------
Graph homework     Algorithms   assignment  2026-06-15   2d left   TODO
Final project      Databases    project     2026-06-20   7d left   DOING
Retake exam        Networks     exam        2026-06-25   12d left  TODO

Urgency
-------
2d left     Graph homework
7d left     Final project
12d left    Retake exam
```

This is essential.

---

# 8. Exam calendar

Command:

```bash
dv exams.csv exam-calendar
```

Output:

```text
EXAM CALENDAR: JUNE 2026

Date        Course             Type      Days Left
----------  -----------------  --------  ---------
2026-06-15  Algorithms         Midterm   2
2026-06-18  Databases          Final     5
2026-06-20  Operating Systems  Final     7
2026-06-25  Networks           Retake    12

Timeline
Jun 13  today
Jun 15  ** Algorithms
Jun 18  ***** Databases
Jun 20  ******* Operating Systems
Jun 25  ************ Networks
```

Alternative compact view:

```text
JUNE 2026 EXAMS

13 today
14 .
15 Algorithms
16 .
17 .
18 Databases
19 .
20 Operating Systems
21 .
22 .
23 .
24 .
25 Networks retake
```

---

# 9. Study allocation by course

Command:

```bash
dv study.csv study-by-course --week current
```

Schema:

```csv
date,course,minutes,topic
2026-06-10,Algorithms,90,graphs
2026-06-11,Databases,60,normalization
2026-06-12,Networks,120,subnetting
```

Output:

```text
STUDY TIME BY COURSE: CURRENT WEEK

Algorithms         ################      4h 30m
Networks           ####################  5h 40m
Databases          ########              2h 10m
Operating Systems  ######                1h 30m

Total: 13h 50m
```

This shows effort distribution.

---

# 10. Study consistency calendar

Command:

```bash
dv study.csv calendar --date date --value minutes
```

Output:

```text
STUDY CALENDAR: 2026

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

This is the university version of GitHub’s contribution graph.

---

# 11. Course topic progress

Command:

```bash
dv topics.csv topic-progress --course Algorithms
```

Schema:

```csv
course,topic,status,confidence
Algorithms,Big O,done,90
Algorithms,Recursion,done,80
Algorithms,Graphs,doing,55
Algorithms,Dynamic Programming,todo,10
```

Output:

```text
TOPIC PROGRESS: Algorithms

Topic                 Status   Confidence   Progress
--------------------  -------  -----------  --------------------
Big O                 done     90%          ##################--
Recursion             done     80%          ################----
Graphs                doing    55%          ###########---------
Dynamic Programming   todo     10%          ##------------------

Course readiness: 58.8%
```

Very useful for exams.

---

# 12. Weak topic detector

Command:

```bash
dv topics.csv weak-topics
```

Output:

```text
WEAK TOPICS

Course       Topic                 Confidence   Status
-----------  --------------------  -----------  -------
Algorithms   Dynamic Programming   10%          todo
Networks     Subnetting            35%          weak
OS           Processes             45%          weak
Databases    Transactions          50%          medium

Priority
--------
1. Algorithms / Dynamic Programming
2. Networks / Subnetting
3. OS / Processes
```

This gives actionable study targets.

---

# 13. Prerequisite graph / dependency view

Command:

```bash
dv courses.csv prereq
```

Schema:

```csv
course,prerequisite,status
Algorithms,Discrete Math,done
Databases,Programming II,done
Operating Systems,Computer Architecture,done
Networks,Computer Architecture,done
Compilers,Algorithms,todo
```

ASCII tree:

```text
COURSE PREREQUISITES

Compilers
`-- Algorithms
    `-- Discrete Math

Networks
`-- Computer Architecture

Operating Systems
`-- Computer Architecture

Databases
`-- Programming II
```

With status:

```text
Compilers [todo]
`-- Algorithms [doing]
    `-- Discrete Math [done]
```

This is powerful for planning semesters.

---

# 14. Retake / failed course view

Command:

```bash
dv university.csv retakes
```

Output:

```text
RETAKES / FAILED COURSES

Course      Semester      Score   Grade   Credits   Action
----------  ------------  ------  ------  --------  ----------------
Networks    2025 Spring   41      F       6         retake required

Impact
------
Lost credits:      6
GPA impact:        high
Graduation risk:   medium
```

This should be blunt. Failed courses are high priority.

---

# 15. Attendance view

Command:

```bash
dv attendance.csv attendance
```

Schema:

```csv
date,course,status
2026-06-01,Algorithms,present
2026-06-02,Databases,absent
2026-06-03,Networks,present
```

Output:

```text
ATTENDANCE

Course             Present   Absent   Rate
-----------------  --------  -------  ------
Algorithms         12        1        92.3%
Databases          10        3        76.9%
Networks           8         5        61.5%

Risk
----
Networks     LOW ATTENDANCE
Databases    WARNING
```

Useful if attendance affects final eligibility.

---

# 16. Grade simulator

Command:

```bash
dv grades.csv simulate --course Algorithms
```

Schema:

```csv
course,item,weight,score
Algorithms,homework,20,90
Algorithms,midterm,30,75
Algorithms,final,50,
```

Output:

```text
GRADE SIMULATOR: Algorithms

Known:
homework    20%   90
midterm     30%   75

Unknown:
final       50%

Current weighted score: 40.5 / 50 known

Needed on final:
For A  / 91:  101.0 impossible
For B+ / 81:   81.0
For B  / 71:   61.0
For C  / 61:   41.0
```

This is extremely useful.

---

# 17. Degree requirement checklist

Command:

```bash
dv requirements.csv degree-check`
```

Schema:

```csv
area,required_credits,completed_credits
Core CS,90,72
Math,30,24
Electives,60,30
General Education,60,60
```

Output:

```text
DEGREE REQUIREMENTS

Area               Required   Completed   Remaining   Progress
-----------------  ---------  ----------  ----------  --------------------
Core CS            90         72          18          ################----
Math               30         24          6           ################----
Electives          60         30          30          ##########----------
General Education  60         60          0           ####################

Total: 186 / 240 credits
```

---

# 18. Weekly study plan

Command:

```bash
dv university.csv study-plan --week current
```

Output:

```text
WEEKLY STUDY PLAN

Priority is based on exam date, risk, and confidence.

Course       Topic                 Hours   Reason
-----------  --------------------  ------  ---------------------
Networks     Subnetting            5h      failed course
Algorithms   Dynamic Programming   4h      weak topic + exam soon
OS           Processes             3h      medium confidence
Databases    Transactions          2h      final review

Total planned: 14h
```

This is where `dv` becomes more than reporting. It becomes decision support.

---

# 19. University report

Command:

```bash
dv university.csv uni-report
```

Output:

```text
UNIVERSITY REPORT

SUMMARY
-------
Current semester: 2026 Spring
Courses:          6
Credits:          36
Completed:        18 / 36
Average score:    86.8
GPA estimate:     3.42

SEMESTER STATUS
---------------
done        ############  3
doing       ########      2
failed      ####          1

RISKS
-----
Networks        failed / retake needed
Algorithms      exam in 7 days
OS              missing assignment

UPCOMING DEADLINES
------------------
2026-06-15  Algorithms   Graph homework
2026-06-18  Databases    Final exam
2026-06-25  Networks     Retake exam

STUDY PRIORITIES
----------------
1. Networks / Subnetting
2. Algorithms / Dynamic Programming
3. OS / Processes
```

This should be the main command.

---

# Best university commands

```bash
dv university.csv uni-summary
dv university.csv uni-report
dv university.csv semester --current
dv university.csv grades
dv university.csv credits
dv university.csv roadmap
dv university.csv risk
dv assignments.csv deadlines
dv exams.csv exam-calendar
dv study.csv study-by-course
dv study.csv calendar --date date --value minutes
dv topics.csv topic-progress --course Algorithms
dv topics.csv weak-topics
dv courses.csv prereq
dv university.csv retakes
dv attendance.csv attendance
dv grades.csv simulate --course Algorithms
dv requirements.csv degree-check
dv university.csv study-plan
```

# Best build order

```text
1. uni-summary
2. grades
3. credits
4. semester progress
5. deadlines
6. exam calendar
7. risk view
8. study-by-course
9. topic-progress
10. grade simulator
11. degree-check
12. uni-report
```

# Highest-value university view

The single best command is:

```bash
dv university.csv uni-report
```

Because it combines:

```text
grades
credits
current semester
risks
deadlines
study priorities
```

The second most useful is:

```bash
dv grades.csv simulate --course <course>
```

Because it answers the most practical question:

```text
What score do I need to pass / get A / avoid failure?
```
