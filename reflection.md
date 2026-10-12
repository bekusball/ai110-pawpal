# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

My initial UML uses four focused classes: `Owner`, `Pet`, `Task`, and `Scheduler`. An `Owner` stores their name, daily available time, and pets. Each `Pet` stores basic information and its care tasks. A `Task` represents a single care need with a title, duration, priority, category, and completion status. The `Scheduler` keeps the planning logic separate from the data model: it sorts tasks, builds a plan that fits the owner's available time, and explains why tasks were selected. The relationships are `Owner → Pet → Task`, while `Scheduler` uses tasks without owning them.

**b. Design changes**

- Did your design change during implementation?
    *Yes*
- If yes, describe at least one change and why you made it.
  - Add **IDs to Owner, Pet, and Task**. Reason: Names and task titles can repeat or change; IDs provide stable identification.
  - Add **a pet association to Task**. Reason: Tasks retain their pet context when combined into one plan.
  - Add **frequency to Task**. Reason: Distinguishes recurring activities from one-time tasks; initially, scheduling supports daily and once.
  - Define **completed as completion of one task occurrence** and replace daily resets with `Scheduler.mark_task_complete()`. Reason: A completed daily task stays in the history while a fresh incomplete task with a new ID is attached to the same pet. One-time tasks stay completed without creating a successor, and repeated completion does not duplicate tasks.
  - Add **due_date to Task** and an optional planning date to `Scheduler.build_daily_plan()`. Reason: Daily successors are due on the completion date plus `timedelta(days=1)`. Planning includes overdue and current tasks while keeping tomorrow's tasks out of today's plan.
  - Add **optional fixed_start_time to Task**. Reason: Some care activities have a specific clock time. Combined with the due date and duration, this defines an interval for checking overlaps, including intervals that cross midnight.
  - Add **Scheduler.filter_tasks()**. Reason: Tasks can be filtered by completion status and exact pet name, with both filters combined when needed. Filtering preserves the original objects and their order.
  - Add **Scheduler.detect_conflicts()**. Reason: The owner may have overlapping tasks for different pets. Reporting incomplete fixed-time overlaps helps identify these conflicts while keeping priority and time-budget selection separate.
  - Add **Owner.get_all_tasks()**. Reason: Provides one place to retrieve tasks across the owner's pets.
  - Change **Scheduler.build_daily_plan() to accept an Owner**. Reason: Gives the scheduler access to all tasks and the owner's time budget.
  - Pass **the time budget into Scheduler.explain_plan()**. Reason: Allows explanations to connect task selection to available time.
  - Keep **domain classes independent of the interface**. Reason: Supports the CLI-first workflow and later Streamlit integration.

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

The scheduler considers priority, duration, completion status, due date, and the owner's available minutes. I focused on urgency and a realistic daily time budget so the plan is useful and achievable. Fixed start times provide conflict warnings across pets, and daily frequency determines whether completion creates a task for tomorrow.

**b. Tradeoffs**

The scheduler considers tasks in priority order, skips any that exceed the remaining budget, and keeps checking later tasks. This can fit a shorter, lower-priority task after a longer task is skipped. It does not guarantee the best possible combination, but the behavior is simple to understand, explain, and test for this project.

---

## 3. AI Collaboration

**a. How you used AI**

I used AI to develop the domain classes, build a CLI demo, add scheduling algorithms and tests, and connect those features to Streamlit. Specific prompts about completion rules, date calculations, filtering, and conflict reporting were the most helpful. Breaking the work into these stages made each change easier to review.

**b. Judgment and verification**

I clarified that one-time tasks should remain completed and that daily tasks should create a separate occurrence due tomorrow. I also chose conflict reporting across all of an owner's pets. I checked those decisions through the CLI output and focused tests before exposing them in the UI, including repeated completion and duplicate-name cases.

---

## 4. Testing and Verification

**a. What you tested**

I tested priority ordering, budget limits, filtering, completion history, daily recurrence, due dates, and fixed-time overlaps, including calendar and midnight boundaries. UI tests check creation, completion and deletion buttons, combined filters, duplicate names, profile isolation, and saved-plan refreshes. These checks help prevent a correct backend from being connected to the wrong task or stale UI state.

**b. Confidence**

The full suite passes 219 tests, so I am confident in the core behaviors and tested UI workflows. The automated UI checks use Streamlit AppTest. I would next check the interface in a live browser across different screen sizes and longer-running sessions, then add and test persistence across browser reloads.

---

## 5. Reflection

**a. What went well**

I am most satisfied with updating the UI to fit the new functionality properly. Users can now see sorted and filtered tasks, complete them, view tomorrow's recurring occurrences, and understand conflict warnings. Connecting these actions to the backend made the app feel usable as a complete workflow.

**b. What you would improve**

I would improve session persistence so profiles, tasks, and plans survive a browser reload, not just Streamlit reruns and profile switches. Browser storage would be one option to explore. That would make the app more useful for tracking care over multiple visits.

**c. Key takeaway**

Working in chunks is the way to go. Starting with a CLI demo made the implementation clearer for both me and the AI. The rough early UI was a useful template: it gave me room to develop my own ideas and creativity before polishing how the app looked and worked.
