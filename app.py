"""Streamlit actions for PawPal+, using the existing UI task list."""

from datetime import date, datetime, time, timedelta

import streamlit as st

from pawpal_system import Owner, Pet, Scheduler, Task


def create_task(
    title: str,
    duration_minutes: int,
    priority: str,
    category: str,
    frequency: str = "daily",
) -> Task:
    """Validate text inputs before letting the domain validate task constraints."""
    if not title.strip():
        raise ValueError("Enter a task title.")
    if not category.strip():
        raise ValueError("Enter a task category.")
    return Task(
        title=title.strip(),
        duration_minutes=duration_minutes,
        priority=priority,
        category=category.strip(),
        frequency=frequency,
    )


def build_owner(
    owner_name: str,
    pet_name: str,
    species: str,
    available_minutes: int,
    task_records: list[dict],
) -> Owner:
    """Build the domain graph for one action without storing domain objects."""
    if not owner_name.strip():
        raise ValueError("Enter an owner name.")
    if not pet_name.strip():
        raise ValueError("Enter a pet name.")

    owner = Owner(name=owner_name.strip(), available_minutes=available_minutes)
    pet = Pet(name=pet_name.strip(), species=species)
    for record in task_records:
        # Defaults also allow tasks added through the original starter UI.
        task = create_task(
            record["title"],
            record["duration_minutes"],
            record["priority"],
            record.get("category", "other"),
            record.get("frequency", "daily"),
        )
        task.completed = record.get("completed", False)
        pet.add_task(task)
    owner.add_pet(pet)
    return owner


def schedule_rows(plan: list[Task], start_time: time) -> list[dict]:
    """Assign consecutive clock slots to the plan chosen by the scheduler."""
    today = date.today()
    next_start = datetime.combine(today, start_time)

    def clock_label(moment: datetime) -> str:
        days_later = (moment.date() - today).days
        suffix = ""
        if days_later:
            suffix = f" (+{days_later} day{'s' if days_later != 1 else ''})"
        return f"{moment:%H:%M}{suffix}"

    rows = []
    for task in plan:
        end = next_start + timedelta(minutes=task.duration_minutes)
        rows.append({
            "Time": f"{clock_label(next_start)}–{clock_label(end)}",
            "Pet": task.pet.name if task.pet else "-",
            "Task": task.title,
            "Minutes": task.duration_minutes,
            "Priority": task.priority,
        })
        next_start = end
    return rows


def render_schedule(owner: Owner, start_time: time) -> None:
    """Run the scheduler and show its plan, explanations, and budget omissions."""
    scheduler = Scheduler()
    plan = scheduler.build_daily_plan(owner)
    used_minutes = sum(task.duration_minutes for task in plan)

    st.subheader(f"{owner.name}'s schedule")
    count, used, remaining = st.columns(3)
    count.metric("Scheduled tasks", len(plan))
    used.metric("Used minutes", used_minutes)
    remaining.metric("Remaining minutes", owner.available_minutes - used_minutes)

    if plan:
        st.table(schedule_rows(plan, start_time))
        st.markdown("### Why these tasks")
        for explanation in scheduler.explain_plan(plan, owner.available_minutes):
            st.write(explanation)
    elif not owner.get_all_tasks():
        st.info("No tasks yet. Add one above before generating a schedule.")
    elif all(task.completed for task in owner.get_all_tasks()):
        st.info("All tasks are already completed.")
    else:
        st.info("No incomplete tasks fit within the available time.")

    selected_ids = {task.id for task in plan}
    skipped = [
        task for task in scheduler.sort_tasks(owner.get_all_tasks())
        if not task.completed and task.id not in selected_ids
    ]
    if skipped:
        st.markdown("### Skipped (insufficient time)")
        st.table([
            {
                "Pet": task.pet.name if task.pet else "-",
                "Task": task.title,
                "Minutes": task.duration_minutes,
                "Priority": task.priority,
            }
            for task in skipped
        ])
    else:
        st.caption("Skipped: none")


def main() -> None:
    st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")
    st.title("🐾 PawPal+")
    st.markdown("Plan care for one pet using your time budget and task priorities.")

    st.subheader("Owner and pet")
    owner_name = st.text_input("Owner name", value="Jordan", key="owner_name")
    pet_name = st.text_input("Pet name", value="Mochi", key="pet_name")
    species = st.selectbox("Species", ["dog", "cat", "other"], key="species")

    # Keep the starter's task list until the session-storage phase is agreed on.
    if "tasks" not in st.session_state:
        st.session_state.tasks = []

    st.subheader("Tasks")
    st.caption("The tasks below belong to the pet entered above.")
    with st.form("add_task_form"):
        task_title = st.text_input("Task title", value="Morning walk", key="task_title")
        duration_col, priority_col = st.columns(2)
        with duration_col:
            duration = st.number_input(
                "Duration (minutes)", min_value=1, max_value=240,
                value=20, step=1, key="duration",
            )
        with priority_col:
            priority = st.selectbox(
                "Priority", ["low", "medium", "high"], index=2, key="priority",
            )
        category = st.text_input("Category", value="exercise", key="category")
        frequency = st.selectbox("Frequency", ["daily", "once"], key="frequency")
        add_task = st.form_submit_button("Add task")

    if add_task:
        try:
            task = create_task(task_title, int(duration), priority, category, frequency)
        except ValueError as error:
            st.error(str(error))
        else:
            st.session_state.tasks.append({
                "title": task.title,
                "duration_minutes": task.duration_minutes,
                "priority": task.priority,
                "category": task.category,
                "frequency": task.frequency,
                "completed": task.completed,
            })
            st.success(f"Added: {task.describe()}")

    if st.session_state.tasks:
        st.write("Current tasks:")
        st.table(st.session_state.tasks)
    else:
        st.info("No tasks yet. Add one above.")

    st.divider()
    st.subheader("Build Schedule")
    st.caption("Tasks run consecutively from the start time, in priority order.")
    with st.form("schedule_form"):
        available_minutes = st.number_input(
            "Available minutes", min_value=0, max_value=1440,
            value=90, step=1, key="available_minutes",
        )
        start_time = st.time_input("Start time", value=time(8), key="start_time")
        generate = st.form_submit_button("Generate schedule")

    if generate:
        try:
            owner = build_owner(
                owner_name, pet_name, species, int(available_minutes),
                st.session_state.tasks,
            )
        except ValueError as error:
            st.error(str(error))
        else:
            render_schedule(owner, start_time)


if __name__ == "__main__":
    main()
