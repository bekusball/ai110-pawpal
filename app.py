"""PawPal's owner-first Streamlit interface.

Domain objects come from pawpal_system. This module coordinates session state,
user actions, table formatting, and page rendering. Session data survives UI
reruns and profile switches; a browser reload starts a fresh session.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

import streamlit as st

from pawpal_system import Owner, Pet, Scheduler, Task


@dataclass
class FormValues:
    """Submitted form values to restore when returning to an owner profile.

    These values are separate from widget state because Streamlit removes
    widgets for profiles that are no longer displayed. Available minutes and
    start time represent form values; a generated plan has its own accepted
    budget on Owner and its own start time on ProfileState.
    """

    pet_name: str = ""
    species: str = "dog"
    selected_pet_id: str | None = None
    task_title: str = "Morning walk"
    duration_minutes: int = 20
    priority: str = "high"
    category: str = "exercise"
    frequency: str = "daily"
    available_minutes: int = 90
    start_time: time = time(8)


@dataclass
class ProfileState:
    """An owner's saved forms and generated schedule for the current session.

    A None plan means no schedule has been generated. An empty list means a
    schedule was generated with no selected tasks. Plans reference the owner's
    existing Task objects so task identity and pet associations stay intact.
    """

    form_values: FormValues = field(default_factory=FormValues)
    plan: list[Task] | None = None
    plan_start_time: time = time(8)


# Session state


def widget_key(owner: Owner, field_name: str) -> str:
    """Scope a widget to an owner ID, including owners with matching names."""
    return f"{owner.id}_{field_name}"


def initialize_session() -> list[Owner]:
    """Initialize session data without replacing existing owners or selections."""
    st.session_state.setdefault("profile_states", {})
    # Carry remembered selections forward when an existing session loads this refactor.
    if "remembered_owner_id" not in st.session_state:
        st.session_state.remembered_owner_id = st.session_state.pop(
            "selected_owner_id", None,
        )
    if "active_owner_id" in st.session_state:
        previous_selection = st.session_state.pop("active_owner_id")
        st.session_state.setdefault("owner_picker", previous_selection)
    return st.session_state.setdefault("owners", [])


def profile_state(owner: Owner) -> ProfileState:
    """Get or create an owner's saved state without rebuilding domain objects."""
    states = st.session_state.profile_states
    if owner.id not in states:
        values = FormValues(
            selected_pet_id=owner.pets[0].id if owner.pets else None,
            available_minutes=owner.available_minutes,
        )
        states[owner.id] = ProfileState(form_values=values)
    elif isinstance(states[owner.id], dict):
        # Convert the previous in-session dictionary once, retaining plan references.
        previous = states[owner.id]
        legacy_values = previous["inputs"].copy()
        legacy_values["selected_pet_id"] = legacy_values.pop("task_pet")
        legacy_values["duration_minutes"] = legacy_values.pop("duration")
        states[owner.id] = ProfileState(
            form_values=FormValues(**legacy_values),
            plan=previous["plan"],
            plan_start_time=previous["plan_start_time"],
        )
    return states[owner.id]


def restore_profile_inputs(owner: Owner, switched_owner: bool) -> None:
    """Restore an owner's forms while preserving incoming edits on normal reruns."""
    values = profile_state(owner).form_values
    if values.selected_pet_id not in {pet.id for pet in owner.pets}:
        values.selected_pet_id = owner.pets[0].id if owner.pets else None
    for field_name, value in vars(values).items():
        if field_name != "selected_pet_id" or value is not None:
            key = widget_key(owner, field_name)
            if switched_owner:
                # Replace stale defaults from hidden forms when returning to a profile.
                st.session_state[key] = value
            else:
                # An ordinary rerun may carry new submitted values; keep those edits.
                st.session_state.setdefault(key, value)


def save_profile_inputs(owner: Owner) -> None:
    """Copy committed widget values into the owner's saved form values.

    Widgets inside forms reach the server on submission. Missing widgets,
    such as task fields when there are no pets, leave their saved values alone.
    """
    values = profile_state(owner).form_values
    for field_name in vars(values):
        key = widget_key(owner, field_name)
        if key in st.session_state:
            setattr(values, field_name, st.session_state[key])


def repair_pet_selection(owner: Owner) -> None:
    """Keep a valid task target after deletion, or clear it when no pets remain.

    Call before rendering the pet dropdown: Streamlit cannot change a widget's
    value through session state after that widget is instantiated in this run.
    """
    values = profile_state(owner).form_values
    key = widget_key(owner, "selected_pet_id")
    selected_pet_id = st.session_state.get(key, values.selected_pet_id)
    if selected_pet_id not in {pet.id for pet in owner.pets}:
        selected_pet_id = owner.pets[0].id if owner.pets else None
    values.selected_pet_id = selected_pet_id
    if selected_pet_id is None:
        st.session_state.pop(key, None)
    else:
        st.session_state[key] = selected_pet_id


def refresh_plan(owner: Owner) -> None:
    """Refresh a generated plan after a task change using the accepted budget.

    A profile with no generated plan stays unscheduled. An existing empty
    plan must be rebuilt too, so the check uses None rather than truthiness.
    """
    state = profile_state(owner)
    if state.plan is not None:
        state.plan = Scheduler().build_daily_plan(owner)


# Owner, pet, and task actions


def create_owner(name: str) -> Owner:
    """Create an unattached owner with a 90-minute budget; reject blank names."""
    if not name.strip():
        raise ValueError("Enter an owner name.")
    return Owner(name=name.strip(), available_minutes=90)


def create_pet(owner: Owner, name: str, species: str) -> Pet:
    """Create and attach a pet to the owner, rejecting a blank name first."""
    if not name.strip():
        raise ValueError("Enter a pet name.")
    pet = Pet(name=name.strip(), species=species)
    owner.add_pet(pet)
    return pet


def create_task(
    title: str,
    duration_minutes: int,
    priority: str,
    category: str,
    frequency: str = "daily",
) -> Task:
    """Create a task after trimming and validating its text fields.

    Raises ValueError for blank text or invalid duration, priority, or
    frequency. The Task model owns validation of those domain constraints.
    """
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


def delete_pets(owner: Owner, pet_ids: set[str]) -> None:
    """Cascade-delete selected pets, repair selection, and refresh their plan.

    Other owners are untouched. Clear each removed pet's task list and each
    task's pet link before refreshing the saved plan.
    """
    for pet in owner.pets:
        if pet.id in pet_ids:
            for task in pet.tasks:
                task.pet = None
            pet.tasks.clear()
    owner.pets[:] = [pet for pet in owner.pets if pet.id not in pet_ids]

    repair_pet_selection(owner)
    refresh_plan(owner)


def delete_tasks(owner: Owner, task_ids: set[str]) -> None:
    """Detach selected tasks from this owner's pets and refresh the saved plan."""
    for pet in owner.pets:
        for task in pet.tasks:
            if task.id in task_ids:
                task.pet = None
        pet.tasks[:] = [task for task in pet.tasks if task.id not in task_ids]
    refresh_plan(owner)


# Table formatting


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


def pet_rows(owner: Owner) -> list[dict]:
    """Build pet display rows, including hidden IDs for reliable deletion."""
    labels = profile_labels(owner.pets)
    return [{"_id": pet.id, "Pet": labels[pet.id]} for pet in owner.pets]


def task_rows(owner: Owner) -> list[dict]:
    """Build task display rows in pet/task insertion order with pet context."""
    labels = profile_labels(owner.pets)
    rows = []
    for pet in owner.pets:
        for task in pet.tasks:
            rows.append({
                "_id": task.id,
                "Pet": labels[pet.id],
                "Task": task.title,
                "Minutes": task.duration_minutes,
                "Priority": task.priority,
                "Category": task.category,
                "Frequency": task.frequency,
                "Completed": task.completed,
            })
    return rows


def schedule_rows(plan: list[Task], start_time: time) -> list[dict]:
    """Assign consecutive clock slots to the plan chosen by the scheduler."""
    today = date.today()
    next_start = datetime.combine(today, start_time)

    def clock_label(moment: datetime) -> str:
        """Label clock times with a day offset when the plan crosses midnight."""
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


def skipped_task_rows(owner: Owner, plan: list[Task]) -> list[dict]:
    """Build priority-ordered rows for due incomplete tasks omitted from the plan."""
    today = date.today()
    selected_ids = {task.id for task in plan}
    return [
        {
            "Pet": task.pet.name if task.pet else "-",
            "Task": task.title,
            "Minutes": task.duration_minutes,
            "Priority": task.priority,
        }
        for task in Scheduler().sort_tasks(owner.get_all_tasks())
        if not task.completed and task.due_date <= today and task.id not in selected_ids
    ]


# Streamlit UI


def deletion_selection(owner: Owner, kind: str, records: list[dict]) -> set[str]:
    """Render a deletion table and return the selected object IDs.

    Records must be nonempty and contain an _id field. Only the Delete
    checkbox is editable; IDs remain hidden and all details are read-only.
    """
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


def render_owner_form(owners: list[Owner]) -> None:
    """Render owner creation and select a newly created profile for this run."""
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
                st.session_state.owner_picker = owner.id
                st.success(f"Created owner profile: {owner.name}")


def render_owner_section(owners: list[Owner]) -> Owner | None:
    """Render profile creation/selection and restore the selected owner's forms."""
    st.subheader("Owner profiles")
    render_owner_form(owners)
    if not owners:
        st.info("Add an owner profile to get started.")
        return None

    labels = profile_labels(owners)
    if st.session_state.get("owner_picker") not in labels:
        remembered = st.session_state.remembered_owner_id
        if remembered not in labels:
            remembered = owners[0].id
        st.session_state.owner_picker = remembered
    owner_id = st.selectbox(
        "Owner profile", list(labels), format_func=labels.__getitem__,
        key="owner_picker",
    )
    owner = next(owner for owner in owners if owner.id == owner_id)
    restore_profile_inputs(owner, st.session_state.remembered_owner_id != owner_id)
    st.session_state.remembered_owner_id = owner_id
    return owner


def render_pet_form(owner: Owner) -> None:
    """Render pet creation and make a successful addition the next task target."""
    with st.expander("Add pet", expanded=not owner.pets):
        with st.form(widget_key(owner, "add_pet_form")):
            name = st.text_input(
                "Pet name", placeholder="e.g. Mochi", key=widget_key(owner, "pet_name"),
            )
            species = st.selectbox(
                "Species", ["dog", "cat", "other"], key=widget_key(owner, "species"),
            )
            submitted = st.form_submit_button("Add pet")
        if submitted:
            try:
                pet = create_pet(owner, name, species)
            except ValueError as error:
                st.error(str(error))
            else:
                profile_state(owner).form_values.selected_pet_id = pet.id
                st.session_state[widget_key(owner, "selected_pet_id")] = pet.id
                st.success(f"Added pet: {pet.name} ({pet.species})")


def render_pet_section(owner: Owner) -> None:
    """Render the owner's pet form and table, or guidance for an empty profile."""
    st.subheader("Pets")
    render_pet_form(owner)
    if owner.pets:
        render_pets(owner)
    else:
        st.info("Add a pet to this owner profile to start adding tasks.")


def render_task_form(owner: Owner) -> None:
    """Render task creation, attach valid tasks, and refresh an existing schedule."""
    labels = profile_labels(owner.pets)
    with st.form(widget_key(owner, "add_task_form")):
        pet_id = st.selectbox(
            "Pet", list(labels), format_func=labels.__getitem__,
            key=widget_key(owner, "selected_pet_id"),
        )
        title = st.text_input(
            "Task title", key=widget_key(owner, "task_title"),
        )
        duration_col, priority_col = st.columns(2)
        with duration_col:
            duration = st.number_input(
                "Duration (minutes)", min_value=1, max_value=240,
                step=1, key=widget_key(owner, "duration_minutes"),
            )
        with priority_col:
            priority = st.selectbox(
                "Priority", ["low", "medium", "high"],
                key=widget_key(owner, "priority"),
            )
        category = st.text_input(
            "Category", key=widget_key(owner, "category"),
        )
        frequency = st.selectbox(
            "Frequency", ["daily", "once"], key=widget_key(owner, "frequency"),
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
            refresh_plan(owner)
            st.success(f"Added: {task.describe()}")


def render_task_section(owner: Owner) -> None:
    """Render task entry and the current-task table for an owner with pets."""
    st.subheader("Tasks")
    render_task_form(owner)
    render_tasks(owner)


def render_pets(owner: Owner) -> None:
    """Display the pet table and apply selected cascade deletions before rerendering."""
    selected = deletion_selection(owner, "pets", pet_rows(owner))
    st.caption("Deleting a pet also deletes all of its tasks.")
    if st.button(
        "🗑️ Delete selected pets", key=widget_key(owner, "delete_pets"),
        disabled=not selected,
    ):
        delete_pets(owner, selected)
        st.rerun()


def render_tasks(owner: Owner) -> None:
    """Display task details and delete selected tasks only from this owner."""
    tasks = owner.get_all_tasks()
    if not tasks:
        st.info("No tasks yet. Add one above.")
        return
    st.write("Current tasks:")
    selected = deletion_selection(owner, "tasks", task_rows(owner))
    if st.button(
        "🗑️ Delete selected tasks", key=widget_key(owner, "delete_tasks"),
        disabled=not selected,
    ):
        delete_tasks(owner, selected)
        st.rerun()


def render_schedule(owner: Owner, plan: list[Task], start_time: time) -> None:
    """Display a stored plan, explanations, and budget omissions."""
    scheduler = Scheduler()
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

    skipped = skipped_task_rows(owner, plan)
    if skipped:
        st.markdown("### Skipped (insufficient time)")
        st.table(skipped)
    else:
        st.caption("Skipped: none")


def render_schedule_form(owner: Owner) -> None:
    """Commit planning inputs on submission and display any saved schedule."""
    st.divider()
    st.subheader("Build Schedule")
    st.caption("Tasks run consecutively from the start time, in priority order.")
    budget_key = widget_key(owner, "available_minutes")
    st.session_state.setdefault(budget_key, owner.available_minutes)
    with st.form(widget_key(owner, "schedule_form")):
        available_minutes = st.number_input(
            "Available minutes", min_value=0, max_value=1440,
            step=1, key=budget_key,
        )
        start_time = st.time_input(
            "Start time", key=widget_key(owner, "start_time"),
        )
        generate = st.form_submit_button("Generate schedule")

    if generate:
        owner.available_minutes = int(available_minutes)
        state = profile_state(owner)
        state.plan = Scheduler().build_daily_plan(owner)
        state.plan_start_time = start_time

    state = profile_state(owner)
    if state.plan is not None:
        render_schedule(owner, state.plan, state.plan_start_time)


# Entrypoint


def main() -> None:
    """Render the page in owner, pet, task, and schedule order."""
    st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")
    st.title("🐾 PawPal+")
    st.markdown("Choose an owner profile, add their pets, and plan their care tasks.")

    owners = initialize_session()
    owner = render_owner_section(owners)
    if owner is None:
        return

    render_pet_section(owner)
    if owner.pets:
        render_task_section(owner)
    render_schedule_form(owner)

    # Save only after rendering/submission has supplied committed widget values.
    save_profile_inputs(owner)


if __name__ == "__main__":
    main()
