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
6. Check the consecutive slots, used/remaining budget, explanations, and skipped tasks. The plan combines tasks across the selected owner's pets. Empty profiles and zero available minutes produce a helpful empty result.

Owner, pet, and task creation use focused forms and validation helpers. They create domain objects and attach them through `Owner.add_pet()` and `Pet.add_task()`. **Generate schedule** calls `Scheduler.build_daily_plan()` and `Scheduler.explain_plan()` for the selected owner. Clock slots are assigned by the UI. Dropdowns select by ID; repeated display names receive numbered labels so separate profiles and pets remain selectable.

The pet and current-task tables have a **Delete** checkbox on each row. Select one or more rows, then use **🗑️ Delete selected pets** or **🗑️ Delete selected tasks** below that table. The other columns are read-only, and the trash button stays disabled until a row is selected. Deletion uses object IDs, so matching names or task titles remain separate. Deleting a pet also deletes all of its tasks and updates the task dropdown to a remaining pet. Deleting the last pet hides Tasks while keeping Build Schedule available. Adding rows clears old deletion marks so they cannot apply to different rows. Select **Generate schedule** again after deleting items to plan the remaining tasks.

Minimal temporary Streamlit state keeps the working owner collection and active selection during the current visit. Each owner contains their pets and tasks. Reloading the browser or starting another visit begins with no profiles; there is no disk or database persistence. Owner-specific form keys keep inputs from leaking between profiles, and each owner's last submitted budget is retained in their working profile. Generated results appear only on submission and disappear on another interaction; select **Generate schedule** again to display a plan.

Deferred follow-ups include stored schedules with refresh after task changes and loading a default profile. Frequency is recorded, but completion controls and new-day resets are also outside this UI pass.

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

The tests cover model validation, pet/task associations, duplicate attachments, independent collections, daily and one-time completion behavior, stable priority ordering, budget limits, completed-task exclusion, and continuing after an oversized task. CLI tests check both budgets, printed times and pet identities, and silent imports. Streamlit tests cover the empty owner-first view, conditional sections, selecting new owners and pets, switching profiles without mixing data or budgets, duplicate names, task assignment, plans across multiple pets, validation, empty results, midnight slots, and repeated generation without changing task completion. They also verify that working data survives reruns while schedule results are not stored, and that a new visit starts empty. Deletion tests cover selecting table rows, duplicate titles, multiple rows across pets, pet-task cascade deletion, dropdown repair, deleting the last pet/task, owner isolation, and clearing selection after adding rows. AppTest does not support direct table-cell interaction, so tests provide the table-edit state a browser sends and exercise the real trash buttons.

Verified test result:

```text
104 passed
```

## 📐 Smarter Scheduling

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | `Scheduler.sort_tasks()` | High, medium, then low priority; insertion order breaks ties; input is unchanged. |
| Budget selection | `Scheduler.build_daily_plan(owner)` | Excludes completed tasks; skips tasks that do not fit and continues considering later tasks. |
| Explanations | `Scheduler.explain_plan(plan, available_minutes)` | One explanation per selected task, with pet context, priority, duration, and remaining budget. |
| Clock slots | CLI `main()` / UI `schedule_rows()` | Displays consecutive start/end times from 08:00 in the CLI or the chosen start time in the UI; tasks have no fixed-time constraints. |
| Recurring tasks | `Task.reset_for_new_day()` | Explicitly resets daily completion; completed one-time tasks stay complete. |

Planning leaves task completion and the owner's budget unchanged. When a high-priority task exceeds the remaining budget, a shorter task with lower priority can still be selected.

## 📸 Demo Walkthrough

1. Install the requirements and run `python main.py`.
2. Check that Jordan's three pets have six scheduled tasks totaling 90 minutes.
3. Read the brief task explanations for priority and budget fit, and check the used/remaining totals.
4. Switch to the commented 55-minute owner-construction line and run the demo again.
5. Check that the four selected tasks end at 08:55 and that Biscuit's walk and Mochi's brushing are listed as skipped.
