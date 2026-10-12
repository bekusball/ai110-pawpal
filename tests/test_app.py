"""Exercise the owner-first UI and its domain action boundaries."""

from datetime import date, time, timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app import create_owner, create_pet, create_task
from pawpal_system import Owner, Pet, Scheduler


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture
def ui() -> AppTest:
    app = AppTest.from_file(str(APP_PATH)).run()
    assert not app.exception
    return app


def submit(ui: AppTest, label: str) -> None:
    # AppTest treats data editors as display elements and omits their state on
    # button clicks. Preserve the table edits that a browser sends with the click.
    for editor in ui.dataframe:
        if editor.key:
            ui.session_state[editor.key] = ui.session_state[editor.key]
    next(button for button in ui.button if button.label == label).click().run()
    assert not ui.exception


def active_owner(ui: AppTest) -> Owner:
    return next(
        owner for owner in ui.session_state.owners
        if owner.id == ui.session_state.owner_picker
    )


def key(ui: AppTest, field: str) -> str:
    return f"{active_owner(ui).id}_{field}"


def add_owner(ui: AppTest, name: str = "Jordan") -> Owner:
    ui.text_input(key="new_owner_name").set_value(name)
    submit(ui, "Add owner")
    return active_owner(ui)


def add_pet(ui: AppTest, name: str = "Mochi", species: str = "dog") -> Pet:
    ui.text_input(key=key(ui, "pet_name")).set_value(name)
    ui.selectbox(key=key(ui, "species")).set_value(species)
    submit(ui, "Add pet")
    return active_owner(ui).pets[-1]


def add_task(
    ui: AppTest, title: str = "Feeding", minutes: int = 10,
    priority: str = "high", pet: Pet | None = None,
) -> None:
    if pet is not None:
        ui.selectbox(key=key(ui, "selected_pet_id")).set_value(pet.id)
    ui.text_input(key=key(ui, "task_title")).set_value(title)
    ui.number_input(key=key(ui, "duration_minutes")).set_value(minutes)
    ui.selectbox(key=key(ui, "priority")).set_value(priority)
    submit(ui, "Add task")


def rows(ui: AppTest, column: str) -> list[dict]:
    return next(
        table.value for table in [*ui.table, *ui.dataframe]
        if column in table.value.columns
    ).drop(columns=["_id", "Delete", "Complete"], errors="ignore").to_dict("records")


def select_for_deletion(ui: AppTest, kind: str, row_indexes: list[int]) -> None:
    editor = next(
        table for table in ui.dataframe
        if ("Category" in table.value.columns) == (kind == "tasks")
    )
    # AppTest has no cell-click API; use the state sent by the table editor.
    ui.session_state[editor.key] = {
        "edited_rows": {index: {"Delete": True} for index in row_indexes},
        "added_rows": [],
        "deleted_rows": [],
    }
    ui.run()
    assert not ui.exception


def select_for_completion(ui: AppTest, row_indexes: list[int]) -> None:
    editor = next(table for table in ui.dataframe if "Category" in table.value.columns)
    ui.session_state[editor.key] = {
        "edited_rows": {index: {"Complete": True} for index in row_indexes},
        "added_rows": [], "deleted_rows": [],
    }
    ui.run()
    assert not ui.exception


@pytest.fixture
def profile(ui: AppTest) -> AppTest:
    add_owner(ui)
    add_pet(ui)
    return ui


def test_initial_view_only_allows_owner_creation(ui: AppTest) -> None:
    assert ui.session_state.owners == []
    assert [header.value for header in ui.subheader] == ["Owner profiles"]
    assert [button.label for button in ui.button] == ["Add owner"]
    assert [field.label for field in ui.text_input] == ["Owner name"]
    assert not ui.selectbox
    assert not ui.table
    assert not ui.dataframe


def test_new_owner_is_selected_and_shows_pets_and_bottom_schedule(ui: AppTest) -> None:
    owner = add_owner(ui, " Jordan ")

    assert owner.name == "Jordan"
    assert owner.available_minutes == 90
    assert owner.pets == []
    assert ui.selectbox(key="owner_picker").value == owner.id
    assert [header.value for header in ui.subheader] == [
        "Owner profiles", "Pets", "Build Schedule",
    ]
    assert ui.number_input(key=key(ui, "available_minutes")).value == 90
    assert ui.time_input(key=key(ui, "start_time")).value == time(8)
    assert "Task title" not in [field.label for field in ui.text_input]


def test_first_pet_reveals_tasks_and_is_the_selected_target(ui: AppTest) -> None:
    add_owner(ui)
    pet = add_pet(ui, " Mochi ", "cat")

    assert pet.name == "Mochi"
    assert pet.species == "cat"
    assert ui.selectbox(key=key(ui, "selected_pet_id")).value == pet.id
    assert ui.selectbox(key=key(ui, "selected_pet_id")).options == ["Mochi (cat)"]
    assert [header.value for header in ui.subheader] == [
        "Owner profiles", "Pets", "Tasks", "Build Schedule",
    ]


def test_adding_another_pet_selects_it_without_moving_existing_tasks(profile: AppTest) -> None:
    first = active_owner(profile).pets[0]
    add_task(profile)
    second = add_pet(profile, "Biscuit")

    assert profile.selectbox(key=key(profile, "selected_pet_id")).value == second.id
    assert first.tasks[0].pet is first
    assert second.tasks == []
    add_task(profile, "Play", 5, "low")
    assert second.tasks[0].pet is second


def test_task_form_routes_to_the_selected_pet_and_displays_all_fields(profile: AppTest) -> None:
    first = active_owner(profile).pets[0]
    second = add_pet(profile, "Luna", "cat")
    profile.text_input(key=key(profile, "category")).set_value(" grooming ")
    profile.selectbox(key=key(profile, "frequency")).set_value("once")
    add_task(profile, " Nail trim ", 15, "low", pet=first)

    assert second.tasks == []
    assert first.tasks[0].pet is first
    assert rows(profile, "Category") == [{
        "Pet": "Mochi (dog)", "Task": "Nail trim", "Minutes": 15,
        "Priority": "low", "Category": "grooming", "Frequency": "once",
        "Due date": date.today(), "Fixed start": "Flexible",
        "Completed": False,
    }]
    assert "Mochi (dog): Nail trim" in profile.success[0].value


def test_duplicate_owner_and_pet_names_remain_independently_selectable(ui: AppTest) -> None:
    first_owner = add_owner(ui, "Jordan")
    first_pet = add_pet(ui, "Mochi")
    second_pet = add_pet(ui, "Mochi")
    assert ui.selectbox(key=key(ui, "selected_pet_id")).options == [
        "Mochi (dog) (1)", "Mochi (dog) (2)",
    ]
    add_task(ui, pet=first_pet)
    assert len(first_pet.tasks) == 1
    assert second_pet.tasks == []

    second_owner = add_owner(ui, "Jordan")
    assert second_owner.id != first_owner.id
    assert ui.selectbox(key="owner_picker").options == ["Jordan (1)", "Jordan (2)"]
    assert active_owner(ui) is second_owner
    assert second_owner.pets == []
    ui.selectbox(key="owner_picker").set_value(first_owner.id).run()
    assert not ui.exception
    assert active_owner(ui) is first_owner
    assert ui.selectbox(key=key(ui, "selected_pet_id")).options == [
        "Mochi (dog) (1)", "Mochi (dog) (2)",
    ]


def test_owner_switching_keeps_pets_tasks_and_budgets_separate(profile: AppTest) -> None:
    first = active_owner(profile)
    add_task(profile, "Jordan's feeding")
    profile.number_input(key=key(profile, "available_minutes")).set_value(15)
    submit(profile, "Generate schedule")

    second = add_owner(profile, "Sam")
    assert "Tasks" not in [header.value for header in profile.subheader]
    assert not profile.table
    assert profile.number_input(key=key(profile, "available_minutes")).value == 90
    add_pet(profile, "Luna", "cat")
    add_task(profile, "Sam's feeding", 5)
    assert [row["Task"] for row in rows(profile, "Category")] == ["Sam's feeding"]
    submit(profile, "Generate schedule")
    assert [row["Task"] for row in rows(profile, "Time")] == ["Sam's feeding"]

    profile.selectbox(key="owner_picker").set_value(first.id).run()
    assert not profile.exception
    assert [row["Task"] for row in rows(profile, "Category")] == ["Jordan's feeding"]
    assert profile.number_input(key=key(profile, "available_minutes")).value == 15
    assert first.pets[0].name == "Mochi"
    assert second.pets[0].name == "Luna"
    assert [metric.value for metric in profile.metric] == ["1", "10", "5"]
    submit(profile, "Generate schedule")
    assert [row["Task"] for row in rows(profile, "Time")] == ["Jordan's feeding"]


def test_plan_combines_pets_and_continues_after_a_task_that_does_not_fit(profile: AppTest) -> None:
    mochi = active_owner(profile).pets[0]
    add_task(profile, "Long appointment", 60, "high")
    add_task(profile, "Brushing", 5, "low")
    luna = add_pet(profile, "Luna", "cat")
    add_task(profile, "Feeding", 10, "high", pet=luna)
    add_task(profile, "Play", 15, "medium", pet=mochi)
    profile.number_input(key=key(profile, "available_minutes")).set_value(30)
    profile.time_input(key=key(profile, "start_time")).set_value(time(9, 30))
    submit(profile, "Generate schedule")

    assert rows(profile, "Time") == [
        {"Time": "09:30–09:40", "Pet": "Luna", "Task": "Feeding", "Minutes": 10, "Priority": "high"},
        {"Time": "09:40–09:55", "Pet": "Mochi", "Task": "Play", "Minutes": 15, "Priority": "medium"},
        {"Time": "09:55–10:00", "Pet": "Mochi", "Task": "Brushing", "Minutes": 5, "Priority": "low"},
    ]
    assert [metric.value for metric in profile.metric] == ["3", "30", "0"]
    assert profile.table[-1].value["Task"].tolist() == ["Long appointment"]
    assert any(
        element.value == "Mochi / Play: medium priority; 15 min fits in 20 min; 5 min left."
        for element in profile.markdown
    )


@pytest.mark.parametrize("budget", [0, 5])
def test_no_task_fits_shows_budget_and_skipped_tasks(profile: AppTest, budget: int) -> None:
    add_task(profile)
    profile.number_input(key=key(profile, "available_minutes")).set_value(budget)
    submit(profile, "Generate schedule")

    assert [metric.value for metric in profile.metric] == ["0", "0", str(budget)]
    assert profile.info[0].value == "No incomplete tasks fit within the available time."
    assert profile.table[-1].value["Task"].tolist() == ["Feeding"]


@pytest.mark.parametrize("with_pet", [False, True])
def test_owner_can_generate_an_empty_plan(ui: AppTest, with_pet: bool) -> None:
    add_owner(ui)
    if with_pet:
        add_pet(ui)
    submit(ui, "Generate schedule")

    assert any("before generating a schedule" in info.value for info in ui.info)
    assert [metric.value for metric in ui.metric] == ["0", "0", "90"]
    assert all("Time" not in table.value.columns for table in ui.table)


def test_blank_owner_name_does_not_create_a_profile(ui: AppTest) -> None:
    ui.text_input(key="new_owner_name").set_value("   ")
    submit(ui, "Add owner")

    assert ui.error[0].value == "Enter an owner name."
    assert ui.session_state.owners == []
    assert [header.value for header in ui.subheader] == ["Owner profiles"]


def test_blank_pet_name_does_not_reveal_tasks(ui: AppTest) -> None:
    owner = add_owner(ui)
    ui.text_input(key=key(ui, "pet_name")).set_value("   ")
    submit(ui, "Add pet")

    assert ui.error[0].value == "Enter a pet name."
    assert owner.pets == []
    assert [header.value for header in ui.subheader] == [
        "Owner profiles", "Pets", "Build Schedule",
    ]


@pytest.mark.parametrize("field", ["task_title", "category"])
def test_blank_task_text_does_not_attach_a_task(profile: AppTest, field: str) -> None:
    profile.text_input(key=key(profile, field)).set_value("   ")
    submit(profile, "Add task")

    assert len(profile.error) == 1
    assert active_owner(profile).get_all_tasks() == []


@pytest.mark.parametrize(
    "duration, priority, frequency",
    [(0, "high", "daily"), (10, "urgent", "daily"), (10, "high", "weekly")],
)
def test_task_creation_uses_domain_constraint_validation(
    duration: int, priority: str, frequency: str,
) -> None:
    with pytest.raises(ValueError):
        create_task("Feeding", duration, priority, "food", frequency)


def test_pet_creation_rejects_blank_names_before_attaching() -> None:
    owner = create_owner("Jordan")
    with pytest.raises(ValueError, match="pet name"):
        create_pet(owner, "   ", "dog")
    assert owner.pets == []


def test_completed_tasks_are_neither_planned_nor_skipped(profile: AppTest) -> None:
    add_task(profile, "Done")
    add_task(profile, "Feeding", 5, "low")
    active_owner(profile).get_all_tasks()[0].completed = True
    submit(profile, "Generate schedule")

    assert [row["Task"] for row in rows(profile, "Time")] == ["Feeding"]
    assert [metric.value for metric in profile.metric] == ["1", "5", "85"]
    assert profile.caption[-1].value == "Skipped: none"
    assert active_owner(profile).get_all_tasks()[0].completed is True


def test_all_completed_tasks_show_completion_guidance(profile: AppTest) -> None:
    add_task(profile)
    task = active_owner(profile).get_all_tasks()[0]
    task.completed = True

    submit(profile, "Generate schedule")

    assert [metric.value for metric in profile.metric] == ["0", "0", "90"]
    assert "All tasks are already completed." in [message.value for message in profile.info]
    assert not profile.table
    assert profile.caption[-1].value == "Skipped: none"


def test_future_tasks_are_not_reported_as_insufficient_time(profile: AppTest) -> None:
    add_task(profile, "Today", 10)
    add_task(profile, "Tomorrow", 5)
    owner = active_owner(profile)
    owner.get_all_tasks()[1].due_date = date.today() + timedelta(days=1)

    submit(profile, "Generate schedule")

    assert [row["Task"] for row in rows(profile, "Time")] == ["Today"]
    assert [metric.value for metric in profile.metric] == ["1", "10", "80"]
    assert profile.caption[-1].value == "Skipped: none"
    assert not any("Skipped (insufficient time)" in heading.value for heading in profile.markdown)


def test_daily_completion_keeps_history_without_skipping_tomorrows_successor(
    profile: AppTest,
) -> None:
    add_task(profile, "Feed", 10)
    owner = active_owner(profile)
    original = owner.get_all_tasks()[0]
    successor = Scheduler().mark_task_complete(owner, original.id)

    submit(profile, "Generate schedule")

    assert successor is not None and successor.pet is original.pet
    assert owner.get_all_tasks() == [original, successor]
    assert [metric.value for metric in profile.metric] == ["0", "0", "90"]
    assert not profile.table
    assert profile.caption[-1].value == "Skipped: none"
    assert [row["Completed"] for row in rows(profile, "Category")] == [True, False]


def test_regenerating_after_a_budget_change_replaces_the_saved_plan(profile: AppTest) -> None:
    add_task(profile, "Walk", 20)
    add_task(profile, "Feed", 5, "low")
    owner = active_owner(profile)
    submit(profile, "Generate schedule")
    first_plan = profile.session_state.profile_states[owner.id].plan
    profile.number_input(key=key(profile, "available_minutes")).set_value(5)
    profile.time_input(key=key(profile, "start_time")).set_value(time(12, 30))

    submit(profile, "Generate schedule")

    state = profile.session_state.profile_states[owner.id]
    assert first_plan == owner.get_all_tasks()
    assert state.plan is not first_plan
    assert state.plan == [owner.get_all_tasks()[1]]
    assert rows(profile, "Time")[0]["Time"] == "12:30–12:35"
    assert [metric.value for metric in profile.metric] == ["1", "5", "0"]
    assert profile.table[-1].value.to_dict("records") == [
        {"Pet": "Mochi", "Task": "Walk", "Minutes": 20, "Priority": "high"},
    ]


def test_adding_a_task_does_not_commit_unsubmitted_schedule_inputs(profile: AppTest) -> None:
    add_task(profile, "Feed", 10)
    owner = active_owner(profile)
    profile.number_input(key=key(profile, "available_minutes")).set_value(20)
    profile.time_input(key=key(profile, "start_time")).set_value(time(9))
    submit(profile, "Generate schedule")
    profile.number_input(key=key(profile, "available_minutes")).set_value(0)
    profile.time_input(key=key(profile, "start_time")).set_value(time(12))

    add_task(profile, "Brush", 5, "low")

    assert owner.available_minutes == 20
    assert profile.session_state.profile_states[owner.id].plan_start_time == time(9)
    assert [row["Time"] for row in rows(profile, "Time")] == ["09:00–09:10", "09:10–09:15"]
    assert [metric.value for metric in profile.metric] == ["2", "15", "5"]


def test_slot_crossing_midnight_labels_the_next_day(profile: AppTest) -> None:
    add_task(profile, "Evening walk", 20)
    profile.time_input(key=key(profile, "start_time")).set_value(time(23, 50))
    submit(profile, "Generate schedule")

    assert rows(profile, "Time")[0]["Time"] == "23:50–00:10 (+1 day)"


def test_repeated_generation_does_not_duplicate_or_complete_tasks(profile: AppTest) -> None:
    add_task(profile)
    task = active_owner(profile).get_all_tasks()[0]
    submit(profile, "Generate schedule")
    first_plan = rows(profile, "Time")
    submit(profile, "Generate schedule")

    assert rows(profile, "Time") == first_plan
    assert active_owner(profile).get_all_tasks() == [task]
    assert task.completed is False


def test_ordinary_rerun_preserves_domain_identity_and_stored_schedule(profile: AppTest) -> None:
    owner = active_owner(profile)
    pet = owner.pets[0]
    add_task(profile)
    task = pet.tasks[0]
    submit(profile, "Generate schedule")
    saved_plan = profile.session_state.profile_states[owner.id].plan
    profile.run()

    assert not profile.exception
    assert active_owner(profile) is owner
    assert owner.pets[0] is pet
    assert pet.tasks[0] is task
    assert profile.session_state.profile_states[owner.id].plan is saved_plan
    assert saved_plan == [task]
    assert saved_plan[0] is task
    assert [metric.value for metric in profile.metric] == ["1", "10", "80"]
    assert profile.button(key=key(profile, "delete_tasks")).disabled


def test_new_visit_starts_with_no_profiles(profile: AppTest) -> None:
    add_task(profile)
    other = AppTest.from_file(str(APP_PATH)).run()

    assert not other.exception
    assert other.session_state.owners == []
    assert other.session_state.profile_states == {}
    assert other.session_state.remembered_owner_id is None
    assert [header.value for header in other.subheader] == ["Owner profiles"]


def test_deletion_buttons_are_disabled_until_table_rows_are_selected(profile: AppTest) -> None:
    add_task(profile)

    assert profile.button(key=key(profile, "delete_pets")).disabled
    assert profile.button(key=key(profile, "delete_tasks")).disabled
    select_for_deletion(profile, "tasks", [0])
    assert not profile.button(key=key(profile, "delete_tasks")).disabled
    assert profile.button(key=key(profile, "delete_pets")).disabled


def test_task_table_deletes_only_selected_duplicate_titles(profile: AppTest) -> None:
    add_task(profile)
    add_task(profile)
    pet = active_owner(profile).pets[0]
    first, second = pet.tasks
    select_for_deletion(profile, "tasks", [0])
    submit(profile, "🗑️ Delete selected tasks")

    assert pet.tasks == [second]
    assert first.pet is None
    assert second.pet is pet
    assert len(rows(profile, "Category")) == 1
    assert profile.button(key=key(profile, "delete_tasks")).disabled
    submit(profile, "Generate schedule")
    assert [metric.value for metric in profile.metric] == ["1", "10", "80"]


def test_task_table_can_delete_rows_across_multiple_pets(profile: AppTest) -> None:
    add_task(profile, "Walk")
    add_task(profile, "Brush")
    first = active_owner(profile).pets[0]
    second = add_pet(profile, "Luna", "cat")
    add_task(profile, "Feed")
    add_task(profile, "Play")
    select_for_deletion(profile, "tasks", [0, 2])
    submit(profile, "🗑️ Delete selected tasks")

    assert [task.title for task in first.tasks] == ["Brush"]
    assert [task.title for task in second.tasks] == ["Play"]
    assert [row["Task"] for row in rows(profile, "Category")] == ["Brush", "Play"]


def test_pet_table_cascades_tasks_and_repairs_the_selected_pet(profile: AppTest) -> None:
    first = active_owner(profile).pets[0]
    add_task(profile, "Walk")
    second = add_pet(profile, "Mochi")
    add_task(profile, "Feed")
    deleted_task = second.tasks[0]
    select_for_deletion(profile, "pets", [1])
    submit(profile, "🗑️ Delete selected pets")

    assert active_owner(profile).pets == [first]
    assert second.tasks == []
    assert deleted_task.pet is None
    assert profile.selectbox(key=key(profile, "selected_pet_id")).value == first.id
    assert profile.selectbox(key=key(profile, "selected_pet_id")).options == ["Mochi (dog)"]
    assert [row["Task"] for row in rows(profile, "Category")] == ["Walk"]
    submit(profile, "Generate schedule")
    assert [row["Task"] for row in rows(profile, "Time")] == ["Walk"]


def test_deleting_an_unselected_pet_preserves_the_task_target(profile: AppTest) -> None:
    second = add_pet(profile, "Luna", "cat")
    select_for_deletion(profile, "pets", [0])
    submit(profile, "🗑️ Delete selected pets")

    assert profile.selectbox(key=key(profile, "selected_pet_id")).value == second.id
    add_task(profile)
    assert second.tasks[0].pet is second


def test_deleting_all_pets_hides_tasks_but_keeps_the_schedule(profile: AppTest) -> None:
    add_task(profile)
    first = active_owner(profile).pets[0]
    second = add_pet(profile, "Luna", "cat")
    add_task(profile)
    select_for_deletion(profile, "pets", [0, 1])
    submit(profile, "🗑️ Delete selected pets")

    assert active_owner(profile).pets == []
    assert first.tasks == second.tasks == []
    assert active_owner(profile).get_all_tasks() == []
    assert key(profile, "selected_pet_id") not in profile.session_state
    assert [header.value for header in profile.subheader] == [
        "Owner profiles", "Pets", "Build Schedule",
    ]
    assert not profile.dataframe
    submit(profile, "Generate schedule")
    assert [metric.value for metric in profile.metric] == ["0", "0", "90"]


def test_deleting_all_tasks_preserves_the_pet_and_task_form(profile: AppTest) -> None:
    add_task(profile)
    pet = active_owner(profile).pets[0]
    select_for_deletion(profile, "tasks", [0])
    submit(profile, "🗑️ Delete selected tasks")

    assert active_owner(profile).pets == [pet]
    assert pet.tasks == []
    assert "Tasks" in [header.value for header in profile.subheader]
    assert len(profile.dataframe) == 1
    add_task(profile, "New task")
    assert pet.tasks[0].title == "New task"


@pytest.mark.parametrize("kind", ["pets", "tasks"])
def test_table_deletion_is_isolated_to_the_selected_owner(profile: AppTest, kind: str) -> None:
    first_owner = active_owner(profile)
    add_task(profile)
    first_task = first_owner.get_all_tasks()[0]
    second_owner = add_owner(profile, "Jordan")
    second_pet = add_pet(profile)
    add_task(profile)
    select_for_deletion(profile, kind, [0])
    submit(profile, f"🗑️ Delete selected {kind}")

    assert first_owner.get_all_tasks() == [first_task]
    assert first_task.pet is first_owner.pets[0]
    assert second_owner.get_all_tasks() == []
    assert (second_pet in second_owner.pets) == (kind == "tasks")


def test_adding_rows_clears_old_deletion_marks(profile: AppTest) -> None:
    add_task(profile, "First")
    select_for_deletion(profile, "tasks", [0])
    add_task(profile, "Second")

    assert [task.title for task in active_owner(profile).get_all_tasks()] == ["First", "Second"]
    assert profile.button(key=key(profile, "delete_tasks")).disabled


def test_profile_forms_pet_selection_and_schedule_restore_after_switching(profile: AppTest) -> None:
    first = active_owner(profile)
    mochi = first.pets[0]
    add_pet(profile, "Luna", "cat")
    profile.text_input(key=key(profile, "category")).set_value("grooming")
    profile.selectbox(key=key(profile, "frequency")).set_value("once")
    add_task(profile, "Nail trim", 15, "low", pet=mochi)
    assert profile.session_state.profile_states[first.id].form_values.task_title == "Nail trim"
    profile.number_input(key=key(profile, "available_minutes")).set_value(25)
    profile.time_input(key=key(profile, "start_time")).set_value(time(9, 30))
    submit(profile, "Generate schedule")
    assert profile.session_state.profile_states[first.id].form_values.task_title == "Nail trim"
    first_plan = rows(profile, "Time")

    second = add_owner(profile, "Sam")
    add_pet(profile, "Biscuit")
    add_task(profile, "Walk", 20)
    profile.number_input(key=key(profile, "available_minutes")).set_value(50)
    profile.time_input(key=key(profile, "start_time")).set_value(time(12, 15))
    submit(profile, "Generate schedule")
    second_plan = rows(profile, "Time")

    profile.selectbox(key="owner_picker").set_value(first.id).run()
    assert not profile.exception
    assert rows(profile, "Time") == first_plan
    assert profile.selectbox(key=key(profile, "selected_pet_id")).value == mochi.id
    assert profile.text_input(key=key(profile, "pet_name")).value == "Luna"
    assert profile.selectbox(key=key(profile, "species")).value == "cat"
    assert profile.text_input(key=key(profile, "task_title")).value == "Nail trim"
    assert profile.number_input(key=key(profile, "duration_minutes")).value == 15
    assert profile.selectbox(key=key(profile, "priority")).value == "low"
    assert profile.text_input(key=key(profile, "category")).value == "grooming"
    assert profile.selectbox(key=key(profile, "frequency")).value == "once"
    assert profile.number_input(key=key(profile, "available_minutes")).value == 25
    assert profile.time_input(key=key(profile, "start_time")).value == time(9, 30)
    assert profile.session_state.remembered_owner_id == first.id

    profile.selectbox(key="owner_picker").set_value(second.id).run()
    assert not profile.exception
    assert rows(profile, "Time") == second_plan
    assert profile.time_input(key=key(profile, "start_time")).value == time(12, 15)


def test_an_existing_empty_schedule_updates_when_the_first_task_is_added(ui: AppTest) -> None:
    owner = add_owner(ui)
    submit(ui, "Generate schedule")
    assert ui.session_state.profile_states[owner.id].plan == []
    add_pet(ui)
    add_task(ui)

    assert [row["Task"] for row in rows(ui, "Time")] == ["Feeding"]
    assert [metric.value for metric in ui.metric] == ["1", "10", "80"]


def test_task_deletion_refreshes_the_plan_with_saved_budget_and_clock_time(profile: AppTest) -> None:
    add_task(profile, "Walk", 20)
    add_task(profile, "Feeding", 10, "low")
    profile.number_input(key=key(profile, "available_minutes")).set_value(20)
    profile.time_input(key=key(profile, "start_time")).set_value(time(9, 30))
    submit(profile, "Generate schedule")
    assert [row["Task"] for row in rows(profile, "Time")] == ["Walk"]

    select_for_deletion(profile, "tasks", [0])
    submit(profile, "🗑️ Delete selected tasks")

    assert [row["Task"] for row in rows(profile, "Time")] == ["Feeding"]
    assert rows(profile, "Time")[0]["Time"] == "09:30–09:40"
    assert [metric.value for metric in profile.metric] == ["1", "10", "10"]


def test_pet_cascade_refreshes_and_stores_only_remaining_tasks(profile: AppTest) -> None:
    owner = active_owner(profile)
    add_task(profile, "Walk", 20)
    luna = add_pet(profile, "Luna", "cat")
    add_task(profile, "Feeding", 5, "low")
    profile.time_input(key=key(profile, "start_time")).set_value(time(11))
    submit(profile, "Generate schedule")
    select_for_deletion(profile, "pets", [0])
    submit(profile, "🗑️ Delete selected pets")

    assert profile.session_state.profile_states[owner.id].plan == luna.tasks
    assert [row["Task"] for row in rows(profile, "Time")] == ["Feeding"]
    assert rows(profile, "Time")[0]["Time"] == "11:00–11:05"
    assert [metric.value for metric in profile.metric] == ["1", "5", "85"]

    add_owner(profile, "Sam")
    assert not profile.metric
    profile.selectbox(key="owner_picker").set_value(owner.id).run()
    assert not profile.exception
    assert [row["Task"] for row in rows(profile, "Time")] == ["Feeding"]
    assert rows(profile, "Time")[0]["Time"] == "11:00–11:05"


def test_deleting_the_last_pet_retains_a_visible_empty_generated_schedule(profile: AppTest) -> None:
    owner = active_owner(profile)
    add_task(profile)
    submit(profile, "Generate schedule")
    select_for_deletion(profile, "pets", [0])
    submit(profile, "🗑️ Delete selected pets")

    assert owner.pets == []
    assert profile.session_state.profile_states[owner.id].plan == []
    assert profile.session_state.profile_states[owner.id].form_values.selected_pet_id is None
    assert not profile.table
    assert not profile.dataframe
    assert [metric.value for metric in profile.metric] == ["0", "0", "90"]
    assert "Tasks" not in [header.value for header in profile.subheader]


def test_task_addition_updates_only_an_owner_with_a_generated_plan(profile: AppTest) -> None:
    first = active_owner(profile)
    add_task(profile)
    submit(profile, "Generate schedule")
    second = add_owner(profile, "Sam")
    add_pet(profile, "Luna", "cat")
    add_task(profile, "Sam's feeding", 5)
    assert profile.session_state.profile_states[second.id].plan is None
    assert not profile.metric

    profile.selectbox(key="owner_picker").set_value(first.id).run()
    assert not profile.exception
    add_task(profile, "Play", 5, "low")
    assert [row["Task"] for row in rows(profile, "Time")] == ["Feeding", "Play"]
    assert [metric.value for metric in profile.metric] == ["2", "15", "75"]
    assert profile.session_state.profile_states[second.id].plan is None


def test_unsubmitted_schedule_inputs_do_not_change_a_saved_plan(profile: AppTest) -> None:
    owner = active_owner(profile)
    add_task(profile)
    submit(profile, "Generate schedule")
    saved_plan = rows(profile, "Time")
    profile.number_input(key=key(profile, "available_minutes")).set_value(0)
    profile.time_input(key=key(profile, "start_time")).set_value(time(12))
    profile.run()

    assert not profile.exception
    assert rows(profile, "Time") == saved_plan
    assert owner.available_minutes == 90
    assert profile.session_state.profile_states[owner.id].plan_start_time == time(8)


def test_invalid_task_submission_keeps_the_generated_schedule(profile: AppTest) -> None:
    add_task(profile)
    submit(profile, "Generate schedule")
    saved_plan = rows(profile, "Time")
    profile.text_input(key=key(profile, "task_title")).set_value("   ")
    submit(profile, "Add task")

    assert len(profile.error) == 1
    assert rows(profile, "Time") == saved_plan
    assert [metric.value for metric in profile.metric] == ["1", "10", "80"]


@pytest.mark.parametrize("valid_selection", [True, False])
def test_session_initialization_restores_a_remembered_owner_or_falls_back(
    valid_selection: bool,
) -> None:
    first = create_owner("Jordan")
    second = create_owner("Sam")
    app = AppTest.from_file(str(APP_PATH))
    app.session_state.owners = [first, second]
    app.session_state.remembered_owner_id = second.id if valid_selection else "missing"
    app.run()

    assert not app.exception
    expected = second if valid_selection else first
    assert app.selectbox(key="owner_picker").value == expected.id
    assert app.session_state.remembered_owner_id == expected.id
    assert app.session_state.owners == [first, second]


def test_existing_session_state_converts_without_losing_forms_or_plan_references() -> None:
    owner = create_owner("Jordan")
    pet = create_pet(owner, "Mochi", "dog")
    task = create_task("Nail trim", 15, "low", "grooming", "once")
    pet.add_task(task)
    owner.available_minutes = 25
    saved_plan = [task]
    app = AppTest.from_file(str(APP_PATH))
    app.session_state.owners = [owner]
    app.session_state.selected_owner_id = owner.id
    app.session_state.active_owner_id = owner.id
    app.session_state.profile_states = {
        owner.id: {
            "inputs": {
                "pet_name": "Mochi",
                "species": "dog",
                "task_pet": pet.id,
                "task_title": "Nail trim",
                "duration": 15,
                "priority": "low",
                "category": "grooming",
                "frequency": "once",
                "available_minutes": 25,
                "start_time": time(9, 30),
            },
            "plan": saved_plan,
            "plan_start_time": time(9, 30),
        },
    }
    app.run()

    assert not app.exception
    state = app.session_state.profile_states[owner.id]
    assert app.session_state.owners[0] is owner
    assert state.plan is saved_plan
    assert state.plan[0] is task
    assert state.form_values.selected_pet_id == pet.id
    assert app.selectbox(key="owner_picker").value == owner.id
    assert app.session_state.remembered_owner_id == owner.id
    assert "selected_owner_id" not in app.session_state
    assert "active_owner_id" not in app.session_state
    assert app.text_input(key=key(app, "task_title")).value == "Nail trim"
    assert app.number_input(key=key(app, "duration_minutes")).value == 15
    assert rows(app, "Time")[0]["Time"] == "09:30–09:45"
    app.run()
    assert not app.exception
    assert app.session_state.profile_states[owner.id] is state
    assert state.plan is saved_plan


def test_task_form_accepts_due_dates_and_optional_fixed_times(profile: AppTest) -> None:
    due = date.today() + timedelta(days=2)
    profile.date_input(key=key(profile, "task_due_date")).set_value(due)
    profile.time_input(key=key(profile, "fixed_start_time")).set_value(time(8, 15))
    add_task(profile, "Appointment", 30)

    task = active_owner(profile).get_all_tasks()[0]
    assert task.due_date == due and task.fixed_start_time == time(8, 15)
    assert rows(profile, "Category")[0]["Due date"] == due
    assert rows(profile, "Category")[0]["Fixed start"] == "08:15"
    assert "No fixed-time overlaps." in [message.value for message in profile.success]
    submit(profile, "Generate schedule")
    assert [metric.value for metric in profile.metric] == ["0", "0", "90"]
    assert "No tasks are due today. Upcoming tasks remain in the task list." in [
        message.value for message in profile.info
    ]


def test_current_tasks_are_priority_sorted_without_reordering_domain_tasks(profile: AppTest) -> None:
    add_task(profile, "Brush", 15, "low")
    add_task(profile, "Play", 10, "medium")
    add_task(profile, "Feed", 5, "high")
    add_task(profile, "Walk", 20, "high")

    assert [row["Task"] for row in rows(profile, "Category")] == ["Feed", "Walk", "Play", "Brush"]
    assert [task.title for task in active_owner(profile).get_all_tasks()] == ["Brush", "Play", "Feed", "Walk"]


def test_status_and_pet_filters_combine_and_distinguish_duplicate_names(profile: AppTest) -> None:
    first = active_owner(profile).pets[0]
    add_task(profile, "First pet")
    second = add_pet(profile, "Mochi", "cat")
    add_task(profile, "Second pet")
    second.tasks[0].completed = True
    submit(profile, "Generate schedule")
    saved_plan = rows(profile, "Time")

    profile.selectbox(key=key(profile, "task_pet_filter_id")).set_value(second.id).run()
    profile.selectbox(key=key(profile, "task_status_filter")).set_value("Completed").run()
    assert [row["Task"] for row in rows(profile, "Category")] == ["Second pet"]
    assert profile.button(key=key(profile, "complete_tasks")).disabled
    profile.selectbox(key=key(profile, "task_status_filter")).set_value("Pending").run()
    assert "No tasks match these filters." in [message.value for message in profile.info]
    assert not any("Category" in table.value.columns for table in profile.dataframe)

    profile.selectbox(key=key(profile, "task_pet_filter_id")).set_value(first.id).run()
    assert [row["Task"] for row in rows(profile, "Category")] == ["First pet"]
    assert rows(profile, "Time") == saved_plan


def test_bulk_completion_creates_daily_successor_and_refreshes_saved_schedule(profile: AppTest) -> None:
    profile.time_input(key=key(profile, "fixed_start_time")).set_value(time(8))
    add_task(profile, "Feed", 10)
    owner = active_owner(profile)
    daily = owner.get_all_tasks()[0]
    second = add_pet(profile, "Luna", "cat")
    profile.time_input(key=key(profile, "fixed_start_time")).set_value(None)
    profile.selectbox(key=key(profile, "frequency")).set_value("once")
    add_task(profile, "Nail trim", 5, "low")
    once = second.tasks[0]
    profile.number_input(key=key(profile, "available_minutes")).set_value(15)
    profile.time_input(key=key(profile, "start_time")).set_value(time(9, 30))
    submit(profile, "Generate schedule")
    profile.number_input(key=key(profile, "available_minutes")).set_value(0)
    profile.time_input(key=key(profile, "start_time")).set_value(time(12))

    select_for_completion(profile, [0, 1])
    submit(profile, "Mark selected complete")

    successor = daily.pet.tasks[-1]
    assert daily.completed is once.completed is True
    assert successor.id != daily.id and successor.completed is False
    assert successor.due_date == date.today() + timedelta(days=1)
    assert successor.fixed_start_time == time(8)
    assert len(owner.get_all_tasks()) == 3
    assert second.tasks == [once]
    assert owner.available_minutes == 15
    assert profile.session_state.profile_states[owner.id].plan_start_time == time(9, 30)
    assert [metric.value for metric in profile.metric] == ["0", "0", "15"]
    assert profile.button(key=key(profile, "complete_tasks")).disabled
    assert any("1 daily occurrence due" in message.value for message in profile.success)
    assert not any("Skipped (insufficient time)" in heading.value for heading in profile.markdown)


def test_once_completion_resets_selection_and_does_not_repeat(profile: AppTest) -> None:
    profile.selectbox(key=key(profile, "frequency")).set_value("once")
    add_task(profile, "Nail trim")
    task = active_owner(profile).get_all_tasks()[0]
    select_for_completion(profile, [0])
    submit(profile, "Mark selected complete")

    assert task.completed is True
    assert active_owner(profile).get_all_tasks() == [task]
    assert profile.button(key=key(profile, "complete_tasks")).disabled
    select_for_completion(profile, [0])
    assert profile.button(key=key(profile, "complete_tasks")).disabled
    assert active_owner(profile).get_all_tasks() == [task]


def test_completion_targets_one_id_when_titles_match(profile: AppTest) -> None:
    add_task(profile, "Feed")
    add_task(profile, "Feed")
    first, second = active_owner(profile).get_all_tasks()
    select_for_completion(profile, [1])
    submit(profile, "Mark selected complete")

    assert first.completed is False and second.completed is True
    assert len(active_owner(profile).get_all_tasks()) == 3


def test_owner_wide_conflict_warning_survives_filters_and_clears_after_completion(profile: AppTest) -> None:
    today = date.today()
    profile.selectbox(key=key(profile, "frequency")).set_value("once")
    profile.time_input(key=key(profile, "fixed_start_time")).set_value(time(23, 50))
    add_task(profile, "Late walk", 20)
    add_pet(profile, "Luna", "cat")
    profile.date_input(key=key(profile, "task_due_date")).set_value(today + timedelta(days=1))
    profile.time_input(key=key(profile, "fixed_start_time")).set_value(time(0, 5))
    add_task(profile, "Feeding", 10)
    luna = active_owner(profile).pets[1]

    assert len(profile.warning) == 1 and "1 fixed-time overlap" in profile.warning[0].value
    conflicts = rows(profile, "First task")
    assert conflicts[0]["First task"] == "Mochi (dog) / Late walk"
    assert conflicts[0]["Second task"] == "Luna (cat) / Feeding"
    assert conflicts[0]["First interval"] == (
        f"{today.isoformat()} 23:50 – {(today + timedelta(days=1)).isoformat()} 00:10"
    )
    profile.selectbox(key=key(profile, "task_pet_filter_id")).set_value(luna.id).run()
    assert rows(profile, "First task") == conflicts
    select_for_completion(profile, [0])
    submit(profile, "Mark selected complete")
    assert not profile.warning
    assert "No fixed-time overlaps." in [message.value for message in profile.success]


def test_filter_changes_clear_stale_deletion_marks(profile: AppTest) -> None:
    add_task(profile, "First pet")
    second = add_pet(profile, "Luna", "cat")
    add_task(profile, "Second pet")
    select_for_deletion(profile, "tasks", [0])
    assert not profile.button(key=key(profile, "delete_tasks")).disabled

    profile.selectbox(key=key(profile, "task_pet_filter_id")).set_value(second.id).run()

    assert profile.button(key=key(profile, "delete_tasks")).disabled
    assert [row["Task"] for row in rows(profile, "Category")] == ["Second pet"]


def test_new_fields_and_filters_restore_per_owner_and_repair_after_pet_deletion(profile: AppTest) -> None:
    first = active_owner(profile)
    pet = first.pets[0]
    due = date.today() + timedelta(days=3)
    profile.date_input(key=key(profile, "task_due_date")).set_value(due)
    profile.time_input(key=key(profile, "fixed_start_time")).set_value(time(10))
    add_task(profile)
    profile.selectbox(key=key(profile, "task_pet_filter_id")).set_value(pet.id).run()
    profile.selectbox(key=key(profile, "task_status_filter")).set_value("Pending").run()
    second = add_owner(profile, "Sam")
    add_pet(profile, "Luna", "cat")
    add_task(profile, "Sam's task")
    assert second.get_all_tasks()[0].fixed_start_time is None

    profile.selectbox(key="owner_picker").set_value(first.id).run()

    assert profile.date_input(key=key(profile, "task_due_date")).value == due
    assert profile.time_input(key=key(profile, "fixed_start_time")).value == time(10)
    assert profile.selectbox(key=key(profile, "task_pet_filter_id")).value == pet.id
    assert profile.selectbox(key=key(profile, "task_status_filter")).value == "Pending"
    select_for_completion(profile, [0])
    submit(profile, "Mark selected complete")
    assert second.get_all_tasks()[0].completed is False
    add_pet(profile, "Biscuit")
    add_task(profile, "Biscuit's task")
    select_for_deletion(profile, "pets", [0])
    submit(profile, "🗑️ Delete selected pets")
    assert profile.selectbox(key=key(profile, "task_pet_filter_id")).value is None
    assert not profile.exception


def test_saved_plan_refreshes_when_the_calendar_day_changes(profile: AppTest) -> None:
    add_task(profile)
    submit(profile, "Generate schedule")
    state = profile.session_state.profile_states[active_owner(profile).id]
    state.plan = []
    state.plan_date = date.today() - timedelta(days=1)

    profile.run()

    assert state.plan_date == date.today()
    assert [row["Task"] for row in rows(profile, "Time")] == ["Feeding"]
