Teacher-specific views fit `dv` well because teaching data usually becomes:

```text
student + class + assignment + score + attendance + topic + date + feedback
```

The goal is not just grading. The real value is:

```text
Who is falling behind?
Which topic failed?
Which assignment was too hard?
What should I reteach?
What feedback should I give?
```

# Recommended teacher schemas

## `students.csv`

```csv
student_id,name,group,email,status
1,Ana,K1,ana@example.com,active
2,Giorgi,K1,giorgi@example.com,active
3,Nino,K2,nino@example.com,active
```

## `grades.csv`

```csv
date,student_id,assignment,type,topic,score,max_score
2026-06-01,1,Quiz 1,quiz,variables,8,10
2026-06-01,2,Quiz 1,quiz,variables,5,10
2026-06-05,1,Homework 1,homework,loops,18,20
```

## `attendance.csv`

```csv
date,student_id,class,status
2026-06-01,1,Python,present
2026-06-01,2,Python,absent
2026-06-01,3,Python,present
```

## `topics.csv`

```csv
date,class,topic,planned_minutes,actual_minutes,covered
2026-06-01,Python,variables,60,70,yes
2026-06-03,Python,loops,60,55,yes
2026-06-05,Python,functions,60,40,partial
```

---

# 1. Teacher dashboard

Command:

```bash
dv grades.csv teacher-summary
```

Output:

```text
TEACHER SUMMARY

Class:        Python
Students:     24
Assignments:  8
Average:      78.4%
Median:       81.0%
Pass rate:    83.3%

Risk
----
At risk students:     4
Missing submissions:  9
Weakest topic:        loops
Hardest assignment:   Quiz 3

Class Performance
-----------------
A range     ######      6
B range     ########    8
C range     #####       5
D range     #           1
F range     ####        4
```

This should be the default teacher view.

---

# 2. Gradebook view

Command:

```bash
dv grades.csv gradebook --students students.csv
```

Output:

```text
GRADEBOOK

Student      Quiz 1   HW 1   Quiz 2   Project   Avg
-----------  -------  -----  -------  --------  ------
Ana          80%      90%    85%      92%       86.8%
Giorgi       50%      65%    58%      70%       60.8%
Nino         95%      88%    91%      94%       92.0%
Mariam       70%      --     75%      80%       75.0%

Legend: -- missing
```

This is essential.

---

# 3. Student profile

Command:

```bash
dv grades.csv student --id 2 --students students.csv
```

Output:

```text
STUDENT PROFILE: Giorgi

Average:       60.8%
Attendance:    72.0%
Missing work:  1
Trend:         improving

Grades
------
Quiz 1      50%   ##########
HW 1        65%   #############
Quiz 2      58%   ###########
Project     70%   ##############

Weak Topics
-----------
loops       52%
functions   58%

Suggested action:
Review loops before moving deeper into functions.
```

This is one of the most useful views for teaching.

---

# 4. At-risk students

Command:

```bash
dv grades.csv at-risk --students students.csv
```

Output:

```text
AT-RISK STUDENTS

Student      Avg    Attendance   Missing   Reason
-----------  -----  -----------  --------  ---------------------
Giorgi       60.8%  72.0%        1         low score + attendance
Mariam       68.0%  88.0%        2         missing submissions
Luka         55.0%  91.0%        0         low scores
Nika         74.0%  60.0%        0         low attendance

Risk Summary
------------
HIGH      ##      2
MEDIUM    ##      2
LOW       #################### 20
```

Risk rules:

```text
average < 60%          high
average < 70%          medium
attendance < 70%       high
missing >= 2           medium/high
declining trend        medium
```

---

# 5. Assignment difficulty

Command:

```bash
dv grades.csv assignment-difficulty
```

Output:

```text
ASSIGNMENT DIFFICULTY

Assignment   Avg     Median   Pass Rate   Missing   Difficulty
-----------  ------  -------  ----------  --------  ----------
Quiz 1       76.0%   78.0%    83.3%       0         normal
HW 1         82.5%   85.0%    91.7%       2         easy
Quiz 2       58.2%   55.0%    54.2%       0         hard
Project      88.0%   90.0%    95.8%       1         easy

Hardest:
Quiz 2, avg 58.2%
```

This tells the teacher whether the class failed or the assignment was badly calibrated.

---

# 6. Topic mastery

Command:

```bash
dv grades.csv topic-mastery
```

Output:

```text
TOPIC MASTERY

Topic        Avg     Pass Rate   Chart
-----------  ------  ----------  --------------------
variables    84.0%   91.7%       #################
loops        61.0%   58.3%       ############
functions    68.5%   70.8%       ##############
arrays       75.2%   83.3%       ###############

Needs reteaching:
1. loops
2. functions
```

This is higher value than raw grades.

---

# 7. Score distribution

Command:

```bash
dv grades.csv score-distribution --assignment "Quiz 2"
```

Output:

```text
SCORE DISTRIBUTION: Quiz 2

0-49      ####        4
50-59     #####       5
60-69     ######      6
70-79     ####        4
80-89     ###         3
90-100    ##          2

Average: 58.2%
Median:  55.0%
```

Good for spotting whether an exam was too hard.

---

# 8. Attendance view

Command:

```bash
dv attendance.csv attendance --students students.csv
```

Output:

```text
ATTENDANCE

Student      Present   Absent   Late   Rate
-----------  --------  -------  -----  ------
Ana          18        1        1      90.0%
Giorgi       14        5        1      70.0%
Nino         20        0        0      100.0%
Mariam       16        3        1      80.0%

Low attendance:
Giorgi       70.0%
```

---

# 9. Attendance calendar

Command:

```bash
dv attendance.csv attendance-calendar --student 2
```

Output:

```text
ATTENDANCE CALENDAR: Giorgi

Jun 2026

01 02 03 04 05 06 07
#  #  .  #  L  .  .

08 09 10 11 12 13 14
#  .  #  #  #  .  .

Legend:
# present
. absent / no class
L late
```

---

# 10. Missing submissions

Command:

```bash
dv grades.csv missing-work --students students.csv
```

Output:

```text
MISSING SUBMISSIONS

Student      Missing Count   Missing Assignments
-----------  -------------   --------------------
Mariam       2               HW 1, Quiz 3
Giorgi       1               Project draft
Nika         1               HW 2

Total missing submissions: 4
```

Very useful for follow-up.

---

# 11. Progress trend

Command:

```bash
dv grades.csv progress-trend --student 2
```

Output:

```text
PROGRESS TREND: Giorgi

Quiz 1      50%   ##########
HW 1        65%   #############
Quiz 2      58%   ###########
Project     70%   ##############

Trend: improving overall, unstable quiz performance
```

Class version:

```text
CLASS PROGRESS TREND

Week 1   68%   #############
Week 2   72%   ##############
Week 3   76%   ###############
Week 4   78%   ################
```

---

# 12. Feedback generator view

Not AI-generated essays. Just structured notes from data.

Command:

```bash
dv grades.csv feedback --student 2
```

Output:

```text
FEEDBACK NOTES: Giorgi

Strengths:
- Improved from 50% to 70%
- Project score is stronger than quiz score

Needs work:
- Loops topic is weak
- Attendance is borderline

Suggested feedback:
You are improving, especially in project work. Focus next on loops and quiz practice. Also, attendance needs to become more stable.
```

This is practical before parent/student meetings.

---

# 13. Class comparison by group

Command:

```bash
dv grades.csv group-compare --group group --students students.csv
```

Output:

```text
GROUP COMPARISON

Group   Students   Avg     Pass Rate   Missing
------  ---------  ------  ----------  --------
K1      12         78.4%   83.3%       4
K2      12         72.1%   75.0%       7

Difference:
K1 is +6.3 percentage points higher.
```

Useful when teaching multiple groups.

---

# 14. Rubric view

Schema:

```csv
student_id,assignment,criterion,score,max_score
1,Project,correctness,35,40
1,Project,style,18,20
1,Project,tests,15,20
1,Project,explanation,16,20
```

Command:

```bash
dv rubric.csv rubric --assignment Project
```

Output:

```text
RUBRIC: Project

Criterion      Avg     Max   Weakness
-------------  ------  ----  ----------------
correctness    82.5%   40    ok
style          71.0%   20    medium
tests          54.0%   20    weak
explanation    76.0%   20    ok

Class weakness:
tests
```

This tells you what to reteach after a project.

---

# 15. Lesson coverage

Command:

```bash
dv topics.csv coverage
```

Output:

```text
LESSON COVERAGE

Topic        Planned   Actual   Covered
-----------  --------  -------  --------
variables    60m       70m      yes
loops        60m       55m      yes
functions    60m       40m      partial
arrays       60m       0m       no

Coverage:
covered      ##########  2
partial      #####       1
not covered  #####       1
```

---

# 16. Reteach queue

Command:

```bash
dv grades.csv reteach
```

Output:

```text
RETEACH QUEUE

Priority   Topic       Reason
---------  ----------  ------------------------------
HIGH       loops       avg 61%, pass rate 58%
MEDIUM     functions   avg 68%, many partial answers
LOW        variables   avg 84%, good mastery

Suggested next lesson:
20-minute review of loops with practice problems.
```

This is one of the best teacher-specific views.

---

# 17. Exam readiness

Command:

```bash
dv grades.csv exam-readiness
```

Output:

```text
EXAM READINESS

Student      Avg     Weak Topics        Readiness
-----------  ------  -----------------  ----------
Ana          88%     none               ready
Giorgi       61%     loops, functions   not ready
Nino         92%     none               ready
Mariam       74%     functions          medium

Class readiness:
ready        ############  12
medium       ########      8
not ready    ####          4
```

---

# 18. Parent/student meeting view

Command:

```bash
dv grades.csv meeting --student 2
```

Output:

```text
MEETING NOTES: Giorgi

Current status:
- Average: 60.8%
- Attendance: 70.0%
- Missing work: 1
- Trend: improving

Strengths:
- Project work improved
- Participates when present

Concerns:
- Loops and functions are weak
- Attendance is borderline

Action plan:
1. Complete missing project draft
2. Review loops
3. Attend next 3 classes
```

This is very practical.

---

# 19. Teacher report

Command:

```bash
dv grades.csv teacher-report
```

Output:

```text
TEACHER REPORT

SUMMARY
-------
Students:      24
Assignments:   8
Average:       78.4%
Pass rate:     83.3%

AT RISK
-------
Giorgi       low score + attendance
Mariam       missing work
Luka         low score

TOPIC MASTERY
-------------
variables    #################  84%
loops        ############      61%
functions    ##############    68%

ASSIGNMENT DIFFICULTY
---------------------
Quiz 2       hard, avg 58.2%
HW 1         easy, avg 82.5%

NEXT TEACHING ACTION
--------------------
Reteach loops before next quiz.
```

This should be the main command.

---

# Best teacher commands

```bash
dv grades.csv teacher-summary
dv grades.csv teacher-report
dv grades.csv gradebook --students students.csv
dv grades.csv student --id 2 --students students.csv
dv grades.csv at-risk --students students.csv
dv grades.csv assignment-difficulty
dv grades.csv topic-mastery
dv grades.csv score-distribution --assignment "Quiz 2"
dv attendance.csv attendance --students students.csv
dv grades.csv missing-work --students students.csv
dv grades.csv progress-trend --student 2
dv grades.csv feedback --student 2
dv grades.csv group-compare --students students.csv
dv rubric.csv rubric --assignment Project
dv topics.csv coverage
dv grades.csv reteach
dv grades.csv exam-readiness
dv grades.csv meeting --student 2
```

# Best build order

```text
1. teacher-summary
2. gradebook
3. student profile
4. at-risk
5. assignment difficulty
6. topic mastery
7. attendance
8. missing work
9. progress trend
10. reteach queue
11. teacher-report
```

# Highest-value views

The best command:

```bash
dv grades.csv teacher-report
```

Because it combines:

```text
class performance
at-risk students
weak topics
hard assignments
next teaching action
```

The second best command:

```bash
dv grades.csv student --id <id>
```

Because teaching decisions often happen student-by-student.

# Privacy rule

For teacher data, keep the app **local-first**.

```text
Do not upload student grades.
Do not use public cloud storage by default.
Do not expose private student data in screenshots.
Use anonymous IDs when exporting reports.
```

For personal use, CSV + local reports is enough.
