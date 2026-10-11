"""Owner-first Streamlit actions with temporary profile working data."""

from collections import Counter
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


def create_owner(name: str) -> Owner:
    """Create an empty owner profile with the initial planning budget."""
    if not name.strip():
        raise ValueError("Enter an owner name.")
    return Owner(name=name.strip(), available_minutes=90)


def create_pet(owner: Owner, name: str, species: str) -> Pet:
    """Validate and attach a new pet to the selected owner."""
    if not name.strip():
        raise ValueError("Enter a pet name.")
    pet = Pet(name=name.strip(), species=species)
    owner.add_pet(pet)
    return pet


def delete_pets(owner: Owner, pet_ids: set[str]) -> None:
    """Remove selected pets and their tasks, then repair the task-form selection."""
    for pet in owner.pets:
        if pet.id in pet_ids:
            for task in pet.tasks:
                task.pet = None
            pet.tasks.clear()
    owner.pets[:] = [pet for pet in owner.pets if pet.id not in pet_ids]

    selection_key = f"{owner.id}_task_pet"
    if not owner.pets:
        st.session_state.pop(selection_key, None)
    elif st.session_state.get(selection_key) not in {pet.id for pet in owner.pets}:
        st.session_state[selection_key] = owner.pets[0].id


def delete_tasks(owner: Owner, task_ids: set[str]) -> None:
    """Remove selected tasks only from pets belonging to this owner."""
    for pet in owner.pets:
        for task in pet.tasks:
            if task.id in task_ids:
                task.pet = None
        pet.tasks[:] = [task for task in pet.tasks if task.id not in task_ids]


def deletion_selection(owner: Owner, kind: str, records: list[dict]) -> set[str]:
    """Keep details read-only and select rows to delete using their hidden IDs."""
    # A changed row set gets fresh selection state so old edits cannot target new rows.
    row_ids = "_".join(record["_id"] for record in records)
    editor_key = f"{owner.id}_{kind}_{row_ids}"
    edited = st.data_editor(
        [{"Delete": False, **record} for record in records],
        key=editor_key,
        hide_index=True,
        column_config={
            "_id": None,
            "Delete": st.column_config.CheckboxColumn(
                "Delete", help=f"Select {kind} to remove with the trash button below.",
            ),
        },
        disabled=list(records[0]),
    )
    return {record["_id"] for record in edited if record["Delete"]}


def profile_labels(profiles: list[Owner] | list[Pet]) -> dict[str, str]:
    """Number repeated display names while keeping IDs as selection values."""
    base_labels = {
        profile.id: (
            f"{profile.name} ({profile.species})"
            if isinstance(profile, Pet) else profile.name
        )
        for profile in profiles
    }
    totals = Counter(base_labels.values())
    occurrences = Counter()
    labels = {}
    for profile_id, label in base_labels.items():
        occurrences[label] += 1
        labels[profile_id] = (
            f"{label} ({occurrences[label]})" if totals[label] > 1 else label
        )
    return labels


def render_owner_form(owners: list[Owner]) -> None:
    with st.expander("Add owner profile", expanded=not owners):
        with st.form("add_owner_form"):
            name = st.text_input(
                "Owner name", placeholder="e.g. Jordan", key="new_owner_name",
            )
            submitted = st.form_submit_button("Add owner")
        if submitted:
            try:
                owner = create_owner(name)
            except ValueError as error:
                st.error(str(error))
            else:
                owners.append(owner)
                # Set the selection before rendering the owner dropdown below.
                st.session_state.active_owner_id = owner.id
                st.success(f"Created owner profile: {owner.name}")


def render_pet_form(owner: Owner) -> None:
    with st.expander("Add pet", expanded=not owner.pets):
        with st.form(f"{owner.id}_add_pet_form"):
            name = st.text_input(
                "Pet name", placeholder="e.g. Mochi", key=f"{owner.id}_pet_name",
            )
            species = st.selectbox(
                "Species", ["dog", "cat", "other"], key=f"{owner.id}_species",
            )
            submitted = st.form_submit_button("Add pet")
        if submitted:
            try:
                pet = create_pet(owner, name, species)
            except ValueError as error:
                st.error(str(error))
            else:
                st.session_state[f"{owner.id}_task_pet"] = pet.id
                st.success(f"Added pet: {pet.name} ({pet.species})")


def render_task_form(owner: Owner) -> None:
    labels = profile_labels(owner.pets)
    with st.form(f"{owner.id}_add_task_form"):
        pet_id = st.selectbox(
            "Pet", list(labels), format_func=labels.__getitem__,
            key=f"{owner.id}_task_pet",
        )
        title = st.text_input(
            "Task title", value="Morning walk", key=f"{owner.id}_task_title",
        )
        duration_col, priority_col = st.columns(2)
        with duration_col:
            duration = st.number_input(
                "Duration (minutes)", min_value=1, max_value=240, value=20,
                step=1, key=f"{owner.id}_duration",
            )
        with priority_col:
            priority = st.selectbox(
                "Priority", ["low", "medium", "high"], index=2,
                key=f"{owner.id}_priority",
            )
        category = st.text_input(
            "Category", value="exercise", key=f"{owner.id}_category",
        )
        frequency = st.selectbox(
            "Frequency", ["daily", "once"], key=f"{owner.id}_frequency",
        )
        submitted = st.form_submit_button("Add task")

    if submitted:
        try:
            task = create_task(title, int(duration), priority, category, frequency)
        except ValueError as error:
            st.error(str(error))
        else:
            pet = next(pet for pet in owner.pets if pet.id == pet_id)
            pet.add_task(task)
            st.success(f"Added: {task.describe()}")


def render_pets(owner: Owner) -> None:
    labels = profile_labels(owner.pets)
    selected = deletion_selection(owner, "pets", [
        {"_id": pet.id, "Pet": labels[pet.id]}
        for pet in owner.pets
    ])
    st.caption("Deleting a pet also deletes all of its tasks.")
    if st.button(
        "🗑️ Delete selected pets", key=f"{owner.id}_delete_pets",
        disabled=not selected,
    ):
        delete_pets(owner, selected)
        st.rerun()


def render_tasks(owner: Owner) -> None:
    tasks = owner.get_all_tasks()
    if not tasks:
        st.info("No tasks yet. Add one above.")
        return
    labels = profile_labels(owner.pets)
    st.write("Current tasks:")
    selected = deletion_selection(owner, "tasks", [
        {
            "_id": task.id,
            "Pet": labels[task.pet.id],
            "Task": task.title,
            "Minutes": task.duration_minutes,
            "Priority": task.priority,
            "Category": task.category,
            "Frequency": task.frequency,
            "Completed": task.completed,
        }
        for task in tasks
    ])
    if st.button(
        "🗑️ Delete selected tasks", key=f"{owner.id}_delete_tasks",
        disabled=not selected,
    ):
        delete_tasks(owner, selected)
        st.rerun()


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


def render_schedule_form(owner: Owner) -> None:
    st.divider()
    st.subheader("Build Schedule")
    st.caption("Tasks run consecutively from the start time, in priority order.")
    budget_key = f"{owner.id}_available_minutes"
    st.session_state.setdefault(budget_key, owner.available_minutes)
    with st.form(f"{owner.id}_schedule_form"):
        available_minutes = st.number_input(
            "Available minutes", min_value=0, max_value=1440,
            step=1, key=budget_key,
        )
        start_time = st.time_input(
            "Start time", value=time(8), key=f"{owner.id}_start_time",
        )
        generate = st.form_submit_button("Generate schedule")

    if generate:
        owner.available_minutes = int(available_minutes)
        render_schedule(owner, start_time)


def main() -> None:
    st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")
    st.title("🐾 PawPal+")
    st.markdown("Choose an owner profile, add their pets, and plan their care tasks.")

    # Only working profiles and selection are kept; schedule storage comes later.
    owners = st.session_state.setdefault("owners", [])
    st.subheader("Owner profiles")
    render_owner_form(owners)
    if not owners:
        st.info("Add an owner profile to get started.")
        return

    labels = profile_labels(owners)
    owner_id = st.selectbox(
        "Owner profile", list(labels), format_func=labels.__getitem__,
        key="active_owner_id",
    )
    owner = next(owner for owner in owners if owner.id == owner_id)

    st.subheader("Pets")
    render_pet_form(owner)
    if owner.pets:
        render_pets(owner)
        st.subheader("Tasks")
        render_task_form(owner)
        render_tasks(owner)
    else:
        st.info("Add a pet to this owner profile to start adding tasks.")

    render_schedule_form(owner)


if __name__ == "__main__":
    main()
