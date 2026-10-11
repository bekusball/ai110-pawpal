"""Exercise the owner-first UI and its domain action boundaries."""

from datetime import time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app import create_owner, create_pet, create_task
from pawpal_system import Owner, Pet


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
        if owner.id == ui.session_state.active_owner_id
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
        ui.selectbox(key=key(ui, "task_pet")).set_value(pet.id)
    ui.text_input(key=key(ui, "task_title")).set_value(title)
    ui.number_input(key=key(ui, "duration")).set_value(minutes)
    ui.selectbox(key=key(ui, "priority")).set_value(priority)
    submit(ui, "Add task")


def rows(ui: AppTest, column: str) -> list[dict]:
    return next(
        table.value for table in [*ui.table, *ui.dataframe]
        if column in table.value.columns
    ).drop(columns=["_id", "Delete"], errors="ignore").to_dict("records")


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
    assert ui.selectbox(key="active_owner_id").value == owner.id
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
    assert ui.selectbox(key=key(ui, "task_pet")).value == pet.id
    assert ui.selectbox(key=key(ui, "task_pet")).options == ["Mochi (cat)"]
    assert [header.value for header in ui.subheader] == [
        "Owner profiles", "Pets", "Tasks", "Build Schedule",
    ]


def test_adding_another_pet_selects_it_without_moving_existing_tasks(profile: AppTest) -> None:
    first = active_owner(profile).pets[0]
    add_task(profile)
    second = add_pet(profile, "Biscuit")

    assert profile.selectbox(key=key(profile, "task_pet")).value == second.id
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
        "Completed": False,
    }]
    assert "Mochi (dog): Nail trim" in profile.success[0].value


def test_duplicate_owner_and_pet_names_remain_independently_selectable(ui: AppTest) -> None:
    first_owner = add_owner(ui, "Jordan")
    first_pet = add_pet(ui, "Mochi")
    second_pet = add_pet(ui, "Mochi")
    assert ui.selectbox(key=key(ui, "task_pet")).options == [
        "Mochi (dog) (1)", "Mochi (dog) (2)",
    ]
    add_task(ui, pet=first_pet)
    assert len(first_pet.tasks) == 1
    assert second_pet.tasks == []

    second_owner = add_owner(ui, "Jordan")
    assert second_owner.id != first_owner.id
    assert ui.selectbox(key="active_owner_id").options == ["Jordan (1)", "Jordan (2)"]
    assert active_owner(ui) is second_owner
    assert second_owner.pets == []
    ui.selectbox(key="active_owner_id").set_value(first_owner.id).run()
    assert not ui.exception
    assert active_owner(ui) is first_owner
    assert ui.selectbox(key=key(ui, "task_pet")).options == [
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

    profile.selectbox(key="active_owner_id").set_value(first.id).run()
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
    saved_plan = profile.session_state.profile_states[owner.id]["plan"]
    profile.run()

    assert not profile.exception
    assert active_owner(profile) is owner
    assert owner.pets[0] is pet
    assert pet.tasks[0] is task
    assert profile.session_state.profile_states[owner.id]["plan"] is saved_plan
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
    assert other.session_state.selected_owner_id is None
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
    assert profile.selectbox(key=key(profile, "task_pet")).value == first.id
    assert profile.selectbox(key=key(profile, "task_pet")).options == ["Mochi (dog)"]
    assert [row["Task"] for row in rows(profile, "Category")] == ["Walk"]
    submit(profile, "Generate schedule")
    assert [row["Task"] for row in rows(profile, "Time")] == ["Walk"]


def test_deleting_an_unselected_pet_preserves_the_task_target(profile: AppTest) -> None:
    second = add_pet(profile, "Luna", "cat")
    select_for_deletion(profile, "pets", [0])
    submit(profile, "🗑️ Delete selected pets")

    assert profile.selectbox(key=key(profile, "task_pet")).value == second.id
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
    assert key(profile, "task_pet") not in profile.session_state
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
    assert profile.session_state.profile_states[first.id]["inputs"]["task_title"] == "Nail trim"
    profile.number_input(key=key(profile, "available_minutes")).set_value(25)
    profile.time_input(key=key(profile, "start_time")).set_value(time(9, 30))
    submit(profile, "Generate schedule")
    assert profile.session_state.profile_states[first.id]["inputs"]["task_title"] == "Nail trim"
    first_plan = rows(profile, "Time")

    second = add_owner(profile, "Sam")
    add_pet(profile, "Biscuit")
    add_task(profile, "Walk", 20)
    profile.number_input(key=key(profile, "available_minutes")).set_value(50)
    profile.time_input(key=key(profile, "start_time")).set_value(time(12, 15))
    submit(profile, "Generate schedule")
    second_plan = rows(profile, "Time")

    profile.selectbox(key="active_owner_id").set_value(first.id).run()
    assert not profile.exception
    assert rows(profile, "Time") == first_plan
    assert profile.selectbox(key=key(profile, "task_pet")).value == mochi.id
    assert profile.text_input(key=key(profile, "pet_name")).value == "Luna"
    assert profile.selectbox(key=key(profile, "species")).value == "cat"
    assert profile.text_input(key=key(profile, "task_title")).value == "Nail trim"
    assert profile.number_input(key=key(profile, "duration")).value == 15
    assert profile.selectbox(key=key(profile, "priority")).value == "low"
    assert profile.text_input(key=key(profile, "category")).value == "grooming"
    assert profile.selectbox(key=key(profile, "frequency")).value == "once"
    assert profile.number_input(key=key(profile, "available_minutes")).value == 25
    assert profile.time_input(key=key(profile, "start_time")).value == time(9, 30)
    assert profile.session_state.selected_owner_id == first.id

    profile.selectbox(key="active_owner_id").set_value(second.id).run()
    assert not profile.exception
    assert rows(profile, "Time") == second_plan
    assert profile.time_input(key=key(profile, "start_time")).value == time(12, 15)


def test_an_existing_empty_schedule_updates_when_the_first_task_is_added(ui: AppTest) -> None:
    owner = add_owner(ui)
    submit(ui, "Generate schedule")
    assert ui.session_state.profile_states[owner.id]["plan"] == []
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

    assert profile.session_state.profile_states[owner.id]["plan"] == luna.tasks
    assert [row["Task"] for row in rows(profile, "Time")] == ["Feeding"]
    assert rows(profile, "Time")[0]["Time"] == "11:00–11:05"
    assert [metric.value for metric in profile.metric] == ["1", "5", "85"]

    add_owner(profile, "Sam")
    assert not profile.metric
    profile.selectbox(key="active_owner_id").set_value(owner.id).run()
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
    assert profile.session_state.profile_states[owner.id]["plan"] == []
    assert profile.session_state.profile_states[owner.id]["inputs"]["task_pet"] is None
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
    assert profile.session_state.profile_states[second.id]["plan"] is None
    assert not profile.metric

    profile.selectbox(key="active_owner_id").set_value(first.id).run()
    assert not profile.exception
    add_task(profile, "Play", 5, "low")
    assert [row["Task"] for row in rows(profile, "Time")] == ["Feeding", "Play"]
    assert [metric.value for metric in profile.metric] == ["2", "15", "75"]
    assert profile.session_state.profile_states[second.id]["plan"] is None


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
    assert profile.session_state.profile_states[owner.id]["plan_start_time"] == time(8)


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
    app.session_state.selected_owner_id = second.id if valid_selection else "missing"
    app.run()

    assert not app.exception
    expected = second if valid_selection else first
    assert app.selectbox(key="active_owner_id").value == expected.id
    assert app.session_state.selected_owner_id == expected.id
    assert app.session_state.owners == [first, second]
