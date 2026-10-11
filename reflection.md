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

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
