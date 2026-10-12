# PawPal+ (Module 2 Project)

**PawPal+** helps a pet owner plan care tasks for their pets. The domain logic runs through a CLI demo and the Streamlit actions in `app.py`.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Run the CLI demo

With the virtual environment active:

```bash
python main.py
```

In Windows PowerShell, you can also run it without activating the environment:

```powershell
.\.venv\Scripts\python.exe main.py
```

`main.py` imports `Owner`, `Pet`, `Task`, and `Scheduler` from `pawpal_system.py`. It creates Jordan, two dogs (Mochi and Biscuit), and one cat (Luna), with three, two, and one tasks respectively. All six tasks fit the default 90-minute budget. The CLI prints today's local date, a chronological table with consecutive slots from 08:00, one brief explanation per selected task, and budget totals.

To try the harder scenario, switch these lines in `main()` by commenting out the default and uncommenting the alternative:

```python
owner = build_demo_owner(available_minutes=90)
# owner = build_demo_owner(available_minutes=55)
```

The 55-minute scenario selects Mochi's walk and feeding, Luna's feeding, and Biscuit's enrichment. Biscuit's walk and Mochi's brushing appear under `Skipped (insufficient time)`. This demonstrates continuing to consider shorter tasks after skipping a task that does not fit the remaining budget.

### Run the algorithms demo

```bash
python main.py --algorithms
```

In Windows PowerShell, without activating the environment:

```powershell
.\.venv\Scripts\python.exe main.py --algorithms
```

This separate, noninteractive demo completes Mochi's daily feeding and a one-time nail trim, displays incomplete and completed tasks using combined status/pet filters, and shows the daily successor excluded from today's plan and included tomorrow. It also reports a fixed-time clash between Mochi's 08:00–08:30 walk and Biscuit's 08:15–08:35 walk, with full dates on both intervals. The default schedule demo and programmatic `main()` keep their existing behavior.

### Run the Streamlit UI

```bash
python -m streamlit run app.py
```

In Windows PowerShell, without activating the environment:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The UI follows an owner-first flow and supports multiple owner profiles and pets:

1. Start by adding an owner profile. There is no preset or default profile. Creating an owner selects that profile and initializes a 90-minute budget.
2. Use the owner dropdown to switch profiles, or add another owner. Each profile has its own pets, tasks, and planning budget.
3. Under the selected owner, add pets with a name and species. Adding a pet attaches it to that owner and selects it as the next task target.
4. Once the owner has at least one pet, the Tasks section appears. Choose a pet inside the Add task form and enter a title, duration, priority, category, and frequency (`daily` or `once`). Blank names, task titles, and categories are rejected.
5. Build Schedule remains at the bottom of every owner profile, including profiles without pets. Set the available minutes and start time (initially 08:00), then select **Generate schedule**.
6. Check the consecutive slots, used/remaining budget, explanations, and skipped tasks. The plan combines tasks across the selected owner's pets. Empty profiles and zero available minutes produce a helpful empty result. Generated results remain visible during other interactions and return when switching back to that profile.

Owner, pet, and task creation use focused forms and validation helpers. They create domain objects and attach them through `Owner.add_pet()` and `Pet.add_task()`. **Generate schedule** calls `Scheduler.build_daily_plan()` and `Scheduler.explain_plan()` for the selected owner. Clock slots are assigned by the UI. Dropdowns select by ID; repeated display names receive numbered labels so separate profiles and pets remain selectable.

The pet and current-task tables have a **Delete** checkbox on each row. Select one or more rows, then use **🗑️ Delete selected pets** or **🗑️ Delete selected tasks** below that table. The other columns are read-only, and the trash button stays disabled until a row is selected. Deletion uses object IDs, so matching names or task titles remain separate. Deleting a pet also deletes all of its tasks and updates the task dropdown to a remaining pet. Deleting the last pet hides Tasks while keeping Build Schedule available. Adding rows clears old deletion marks so they cannot apply to different rows. Adding or deleting tasks, including pet-task cascade deletion, automatically refreshes an already-generated schedule using that owner's last accepted budget and start time.

Session state keeps the owner collection, remembers the selected owner, and stores form values and a generated plan separately for each owner ID. Owners continue to contain their own pets and tasks; plans reference those same task objects. Submitted pet/task form values, the selected pet, budget, and start time are restored when switching profiles, even after Streamlit clears hidden widgets. A profile without a generated plan stays unscheduled until **Generate schedule** is selected. Once generated, an empty plan also stays visible and refreshes when tasks are added. Changing the schedule form takes effect on submission; unsubmitted edits do not change the displayed plan.

If the owner dropdown needs to be restored, it selects the session's remembered owner or the first existing owner as a fallback. A fresh browser session starts with no profiles. Storage lasts for the active Streamlit session: browser refresh, a new visit, or restarting the app begins fresh. There is no disk or database persistence. Tasks default to today's due date. Filtering, occurrence completion, and fixed-time conflict reporting are demonstrated through domain methods and the algorithms CLI demo. Streamlit controls for these features, due dates, and fixed start times are deferred to a later phase.

### Code organization

`app.py` groups session-state helpers, owner/pet/task actions, table formatting, and Streamlit rendering. `main()` follows the visible owner → pets → tasks → schedule flow. `FormValues` defines the saved form fields, and `ProfileState` holds those values plus a generated plan and its accepted start time. The owner dropdown uses `owner_picker`; `remembered_owner_id` stores the selection independently of the widget.

`pet_rows()`, `task_rows()`, and the schedule-row helpers build table data separately from rendering. `repair_pet_selection()` handles dropdown repair after cascade deletion. Docstrings describe validation, side effects, and state lifetimes; comments explain widget-restoration timing and why an empty generated plan differs from an ungenerated plan. Existing sessions using the previous dictionary representation are converted once while preserving owner, pet, task, and plan references.

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments and verify it with `python main.py`.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

The default demo (the date changes with the machine's local date):

```text
Jordan's schedule | 2026-10-11 | Budget: 90 min

Time         Pet      Task          Min  Priority
-----------  -------  ------------  ---  --------
08:00-08:30  Mochi    Morning walk   30  HIGH
08:30-08:40  Mochi    Feeding        10  HIGH
08:40-09:00  Biscuit  Morning walk   20  HIGH
09:00-09:05  Luna     Feeding         5  HIGH
09:05-09:15  Biscuit  Enrichment     10  MEDIUM
09:15-09:30  Mochi    Brushing       15  LOW

6 tasks | Used: 90 min | Remaining: 0 min

Why these tasks:
  - Mochi / Morning walk: high priority; 30 min fits in 90 min; 60 min left.
  - Mochi / Feeding: high priority; 10 min fits in 60 min; 50 min left.
  - Biscuit / Morning walk: high priority; 20 min fits in 50 min; 30 min left.
  - Luna / Feeding: high priority; 5 min fits in 30 min; 25 min left.
  - Biscuit / Enrichment: medium priority; 10 min fits in 25 min; 15 min left.
  - Mochi / Brushing: low priority; 15 min fits in 15 min; 0 min left.

Skipped: none
```

The harder scenario prints a compact skipped-task table:

```text
Skipped (insufficient time):
Pet      Task          Min
-------  ------------  ---
Biscuit  Morning walk   20
Mochi    Brushing       15
```

## 🧪 Testing PawPal+

```bash
python -m pytest -q
```

The tests cover model validation, pet/task associations, duplicate attachments, independent collections, daily and one-time completion behavior, stable priority ordering, budget limits, completed-task exclusion, and continuing after an oversized task. Algorithm tests cover combined filters, duplicate pet names, retained completion history, fresh successor IDs, repeated completion, owner isolation, calendar rollover, overdue/future planning, and fixed-time conflicts across pets and midnight. CLI tests check both budgets, printed times and pet identities, the algorithms flag, help output, and silent imports. Streamlit tests cover the empty owner-first view, conditional sections, selecting new owners and pets, switching profiles without mixing data or budgets, duplicate names, task assignment, plans across multiple pets, validation, empty results, midnight slots, and repeated generation without changing task completion. Session tests check domain identity and saved schedules across reruns, restoring forms and plans after profile switching, owner-selection fallback, automatic refresh after additions and deletions, visible empty plans, and preserving schedules during unsubmitted edits or invalid task submissions. A new visit still starts empty. Deletion tests cover selecting table rows, duplicate titles, multiple rows across pets, pet-task cascade deletion, dropdown repair, deleting the last pet/task, owner isolation, and clearing selection after adding rows. AppTest does not support direct table-cell interaction, so tests provide the table-edit state a browser sends and exercise the real trash buttons.

Additional scheduling tests check budget boundaries across pets, replanning with changed budgets, insertion order for overdue priority ties, Unicode pet-name matching, recurrence over multiple days, completion isolation, and conflicts across calendar boundaries and multi-day intervals. UI helper tests check trimmed inputs, independent profile defaults, duplicate pet labels, retained task history, and exact-midnight/multi-day clock labels. Regression tests ensure future tasks, including daily successors, stay out of the UI's insufficient-time table. UI and CLI tests also check all-completed plans, zero budgets, single-task output, replacing a generated plan, and refreshing a plan while schedule-form edits remain unsubmitted.

To run only scheduling tests or UI tests:

```bash
python -m pytest -q tests/test_scheduler.py
python -m pytest -q tests/test_app.py tests/test_app_helpers.py
```

Verified test result:

```text
209 passed
```

## 📐 Smarter Scheduling

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Filtering | `Scheduler.filter_tasks(tasks, completed=None, pet_name=None)` | Status and pet filters combine with AND. Pet names match exactly after trimming and case folding; duplicate names match all corresponding pets. Returns a new list with the original objects in input order. |
| Task sorting | `Scheduler.sort_tasks()` | High, medium, then low priority; insertion order breaks ties; input is unchanged. |
| Budget selection | `Scheduler.build_daily_plan(owner, plan_date=None)` | Defaults to today; includes incomplete tasks due on or before that date. Skips future tasks and tasks that do not fit, continuing to consider later tasks. |
| Explanations | `Scheduler.explain_plan(plan, available_minutes)` | One explanation per selected task, with pet context, priority, duration, and remaining budget. |
| Clock slots | CLI `main()` / UI `schedule_rows()` | Displays consecutive start/end times from 08:00 in the CLI or the chosen start time in the UI. Fixed start times are used for separate conflict reports. |
| Completion and recurrence | `Scheduler.mark_task_complete(owner, task_id, today=None)` | Retains the completed occurrence. Daily tasks create a fresh incomplete successor for the same pet due tomorrow; once tasks create no successor. |
| Conflict detection | `Scheduler.detect_conflicts(tasks)` | Returns unique overlapping `(Task, Task)` pairs for incomplete fixed-time tasks, in input pair order. Pass `owner.get_all_tasks()` to include all the owner's pets. Adjacent intervals do not conflict. |

Planning leaves task completion and the owner's budget unchanged. When a high-priority task exceeds the remaining budget, a shorter task with lower priority can still be selected.

`Task.due_date` defaults to `date.today()` and `fixed_start_time` defaults to `None`. Due dates are calendar dates and fixed start times are local clock times without timezone information. The optional filtering arguments, completion date, and planning date are keyword-only.

Completing a daily task copies its title, duration, priority, category, frequency, and fixed start time to a new task with a new ID. Its due date is based on the completion date, including when the original task was overdue:

```python
from datetime import date, timedelta

tomorrow = date.today() + timedelta(days=1)
successor = Scheduler().mark_task_complete(owner, task.id)
```

`timedelta(days=1)` handles month, year, and leap-day rollover. The successor is returned for daily tasks; one-time and already-completed tasks return `None`. Repeating completion does not add another occurrence. An unknown task ID, including an ID belonging to another owner, raises `ValueError` without changing tasks. This replaces the former `Task.reset_for_new_day()` API: completed occurrences remain completed.

Conflict detection combines each incomplete task's due date and fixed start time with its duration, so intervals crossing midnight are compared accurately. Tasks without fixed start times and completed tasks are excluded. Reports can include future dated occurrences and do not alter the priority/budget plan or assign new clock slots. The CLI demos use fresh in-memory data each run; there is no persistence.

## 📸 Demo Walkthrough

1. Install the requirements and run `python main.py`.
2. Check that Jordan's three pets have six scheduled tasks totaling 90 minutes.
3. Read the brief task explanations for priority and budget fit, and check the used/remaining totals.
4. Switch to the commented 55-minute owner-construction line and run the demo again.
5. Check that the four selected tasks end at 08:55 and that Biscuit's walk and Mochi's brushing are listed as skipped.
6. Run `python main.py --algorithms` to check status/pet filters, retained completed occurrences, tomorrow's daily feeding, one-time completion, and the conflict between the two dogs' walks.
