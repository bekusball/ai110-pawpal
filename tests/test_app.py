"""Exercise the Streamlit actions and their connection to the domain model."""

from datetime import time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app import build_owner


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture
def ui() -> AppTest:
    app = AppTest.from_file(str(APP_PATH)).run()
    assert not app.exception
    return app


def submit(ui: AppTest, label: str) -> None:
    next(button for button in ui.button if button.label == label).click().run()
    assert not ui.exception


def add_task(ui: AppTest, title: str, minutes: int, priority: str) -> None:
    ui.text_input(key="task_title").set_value(title)
    ui.number_input(key="duration").set_value(minutes)
    ui.selectbox(key="priority").set_value(priority)
    submit(ui, "Add task")


def test_add_task_validates_and_displays_domain_fields(ui: AppTest) -> None:
    ui.text_input(key="category").set_value(" grooming ")
    ui.selectbox(key="frequency").set_value("once")
    add_task(ui, " Nail trim ", 15, "low")

    assert ui.table[0].value.to_dict("records") == [{
        "title": "Nail trim",
        "duration_minutes": 15,
        "priority": "low",
        "category": "grooming",
        "frequency": "once",
        "completed": False,
    }]
    assert "Nail trim (15 min) [priority: low, category: grooming]" in ui.success[0].value


def test_generate_uses_current_owner_pet_budget_and_start_time(ui: AppTest) -> None:
    ui.text_input(key="owner_name").set_value(" Sam ")
    ui.text_input(key="pet_name").set_value(" Luna ")
    ui.selectbox(key="species").set_value("cat")
    add_task(ui, "Long appointment", 60, "high")
    add_task(ui, "Brushing", 5, "low")
    add_task(ui, "Feeding", 10, "high")
    add_task(ui, "Play", 15, "medium")

    ui.number_input(key="available_minutes").set_value(30)
    ui.time_input(key="start_time").set_value(time(9, 30))
    submit(ui, "Generate schedule")

    assert ui.subheader[-1].value == "Sam's schedule"
    assert ui.table[1].value.to_dict("records") == [
        {"Time": "09:30–09:40", "Pet": "Luna", "Task": "Feeding", "Minutes": 10, "Priority": "high"},
        {"Time": "09:40–09:55", "Pet": "Luna", "Task": "Play", "Minutes": 15, "Priority": "medium"},
        {"Time": "09:55–10:00", "Pet": "Luna", "Task": "Brushing", "Minutes": 5, "Priority": "low"},
    ]
    assert [metric.value for metric in ui.metric] == ["3", "30", "0"]
    assert ui.table[2].value["Task"].tolist() == ["Long appointment"]
    assert any(
        element.value == "Luna / Play: medium priority; 15 min fits in 20 min; 5 min left."
        for element in ui.markdown
    )


@pytest.mark.parametrize("budget", [0, 5])
def test_no_task_fits_shows_unused_budget_and_skipped_tasks(
    ui: AppTest, budget: int,
) -> None:
    add_task(ui, "Feeding", 10, "high")
    ui.number_input(key="available_minutes").set_value(budget)
    submit(ui, "Generate schedule")

    assert [metric.value for metric in ui.metric] == ["0", "0", str(budget)]
    assert ui.info[0].value == "No incomplete tasks fit within the available time."
    assert ui.table[1].value["Task"].tolist() == ["Feeding"]


def test_generate_without_tasks_is_a_useful_empty_result(ui: AppTest) -> None:
    submit(ui, "Generate schedule")

    assert any("before generating a schedule" in info.value for info in ui.info)
    assert not ui.table
    assert [metric.value for metric in ui.metric] == ["0", "0", "90"]


@pytest.mark.parametrize("field", ["task_title", "category"])
def test_blank_task_text_is_rejected_without_adding_a_record(
    ui: AppTest, field: str,
) -> None:
    ui.text_input(key=field).set_value("   ")
    submit(ui, "Add task")

    assert len(ui.error) == 1
    assert ui.session_state.tasks == []
    assert not ui.table


@pytest.mark.parametrize("field", ["owner_name", "pet_name"])
def test_blank_identity_is_rejected_without_generating_a_plan(
    ui: AppTest, field: str,
) -> None:
    add_task(ui, "Feeding", 10, "high")
    ui.text_input(key=field).set_value("   ")
    submit(ui, "Generate schedule")

    assert len(ui.error) == 1
    assert not ui.metric
    assert len(ui.table) == 1


def test_existing_records_keep_defaults_and_completion_when_building_owner() -> None:
    records = [
        {"title": "Walk", "duration_minutes": 20, "priority": "high"},
        {
            "title": "Nail trim", "duration_minutes": 10, "priority": "low",
            "category": "grooming", "frequency": "once", "completed": True,
        },
    ]

    owner = build_owner("Jordan", "Mochi", "dog", 30, records)

    pet = owner.pets[0]
    assert pet.species == "dog"
    assert all(task.pet is pet for task in owner.get_all_tasks())
    assert pet.tasks[0].category == "other"
    assert pet.tasks[0].frequency == "daily"
    assert pet.tasks[0].completed is False
    assert pet.tasks[1].completed is True
    assert records[0] == {"title": "Walk", "duration_minutes": 20, "priority": "high"}


def test_completed_tasks_are_neither_planned_nor_shown_as_skipped(ui: AppTest) -> None:
    ui.session_state.tasks = [
        {"title": "Done", "duration_minutes": 10, "priority": "high", "completed": True},
        {"title": "Feeding", "duration_minutes": 5, "priority": "low"},
    ]
    submit(ui, "Generate schedule")

    assert ui.table[1].value["Task"].tolist() == ["Feeding"]
    assert len(ui.table) == 2
    assert [metric.value for metric in ui.metric] == ["1", "5", "85"]
    assert ui.caption[-1].value == "Skipped: none"
    assert ui.session_state.tasks[0]["completed"] is True


def test_slot_crossing_midnight_labels_the_next_day(ui: AppTest) -> None:
    add_task(ui, "Evening walk", 20, "high")
    ui.time_input(key="start_time").set_value(time(23, 50))
    submit(ui, "Generate schedule")

    assert ui.table[1].value["Time"].tolist() == ["23:50–00:10 (+1 day)"]


def test_repeated_generation_does_not_duplicate_or_complete_tasks(ui: AppTest) -> None:
    add_task(ui, "Feeding", 10, "high")
    submit(ui, "Generate schedule")
    first_plan = ui.table[1].value.to_dict("records")
    submit(ui, "Generate schedule")

    assert ui.table[1].value.to_dict("records") == first_plan
    assert len(ui.session_state.tasks) == 1
    assert ui.session_state.tasks[0]["completed"] is False


def test_ordinary_rerun_does_not_add_a_task_or_save_a_plan(ui: AppTest) -> None:
    add_task(ui, "Feeding", 10, "high")
    submit(ui, "Generate schedule")
    ui.text_input(key="owner_name").set_value("Sam").run()

    assert not ui.exception
    assert len(ui.session_state.tasks) == 1
    assert len(ui.table) == 1
    assert not ui.metric
