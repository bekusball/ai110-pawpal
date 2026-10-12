"""Check display data directly without starting a Streamlit session."""

from datetime import date, time, timedelta

import pytest

from app import (
    FormValues, ProfileState, create_owner, create_pet, create_task,
    pet_rows, profile_labels, schedule_rows, skipped_task_rows, task_rows,
)
from pawpal_system import Owner, Pet, Task


def test_creation_trims_text_and_retains_task_configuration() -> None:
    owner = create_owner("  Jordan  ")
    pet = create_pet(owner, "  Mochi  ", "dog")
    task = create_task("  Nail trim  ", 15, "low", "  grooming  ", "once")
    pet.add_task(task)

    assert owner.name == "Jordan"
    assert owner.available_minutes == 90
    assert pet.name == "Mochi"
    assert owner.pets == [pet]
    assert (task.title, task.category, task.frequency) == ("Nail trim", "grooming", "once")
    assert task.pet is pet


def test_profile_defaults_do_not_share_forms_or_generated_plans() -> None:
    first = ProfileState()
    second = ProfileState()
    first.form_values.task_title = "Feed"
    first.plan = []

    assert second.form_values == FormValues()
    assert first.form_values is not second.form_values
    assert second.plan is None


def test_duplicate_pet_labels_group_by_name_and_species_and_keep_ids() -> None:
    dog = Pet("Mochi", "dog")
    cat = Pet("Mochi", "cat")
    other_dog = Pet("Mochi", "dog")
    owner = Owner("Jordan", 30, pets=[dog, cat, other_dog])

    assert profile_labels(owner.pets) == {
        dog.id: "Mochi (dog) (1)",
        cat.id: "Mochi (cat)",
        other_dog.id: "Mochi (dog) (2)",
    }
    assert pet_rows(owner) == [
        {"_id": pet.id, "Pet": label}
        for pet, label in zip(owner.pets, ["Mochi (dog) (1)", "Mochi (cat)", "Mochi (dog) (2)"])
    ]
    assert profile_labels([]) == {}


def test_task_rows_retain_completed_history_and_distinct_ids() -> None:
    pet = Pet("Mochi", "dog")
    completed = Task("Feed", 10, "high", "food", completed=True)
    pending = Task("Feed", 10, "high", "food")
    for task in (completed, pending):
        pet.add_task(task)
    owner = Owner("Jordan", 20, pets=[pet])

    records = task_rows(owner)

    assert records == [
        {
            "_id": task.id, "Pet": "Mochi (dog)", "Task": "Feed",
            "Minutes": 10, "Priority": "high", "Category": "food",
            "Frequency": "daily", "Completed": done,
            "Due date": date.today(), "Fixed start": "Flexible",
        }
        for task, done in ((completed, True), (pending, False))
    ]
    records.clear()
    assert pet.tasks == [completed, pending]


@pytest.mark.parametrize("start, duration, expected", [
    (time(8), 10, "08:00–08:10"),
    (time(23, 50), 10, "23:50–00:00 (+1 day)"),
    (time(0), 1440, "00:00–00:00 (+1 day)"),
    (time(23, 50), 1450, "23:50–00:00 (+2 days)"),
])
def test_schedule_rows_label_exact_midnight_and_multiple_days(
    start: time, duration: int, expected: str,
) -> None:
    task = Task("Care", duration, "high", "care")

    assert schedule_rows([task], start) == [{
        "Time": expected, "Pet": "-", "Task": "Care",
        "Minutes": duration, "Priority": "high",
    }]
    assert task.pet is None and task.completed is False


def test_schedule_rows_continue_after_a_multi_day_slot_without_changing_tasks() -> None:
    long = Task("Long care", 1450, "high", "care", fixed_start_time=time(8))
    short = Task("Feed", 10, "low", "food")
    plan = [long, short]

    records = schedule_rows(plan, time(23, 50))

    assert [row["Time"] for row in records] == [
        "23:50–00:00 (+2 days)", "00:00 (+2 days)–00:10 (+2 days)",
    ]
    assert plan == [long, short]
    assert long.fixed_start_time == time(8)
    assert schedule_rows([], time(8)) == []


def test_skipped_rows_include_only_due_incomplete_tasks_outside_the_plan() -> None:
    today = date.today()
    pet = Pet("Mochi", "dog")
    low = Task("Brush", 15, "low", "care", due_date=today)
    selected = Task("Feed", 10, "high", "food", due_date=today)
    future = Task("Tomorrow", 5, "high", "care", due_date=today + timedelta(days=1))
    overdue = Task("Overdue walk", 30, "high", "care", due_date=today - timedelta(days=1))
    done = Task("Done", 5, "high", "care", completed=True, due_date=today)
    for task in (low, selected, future, overdue, done):
        pet.add_task(task)
    owner = Owner("Jordan", 10, pets=[pet])

    assert skipped_task_rows(owner, [selected]) == [
        {"Pet": "Mochi", "Task": "Overdue walk", "Minutes": 30, "Priority": "high"},
        {"Pet": "Mochi", "Task": "Brush", "Minutes": 15, "Priority": "low"},
    ]
    assert pet.tasks == [low, selected, future, overdue, done]


def test_empty_owner_tables_have_no_rows() -> None:
    owner = Owner("Jordan", 0)

    assert pet_rows(owner) == []
    assert task_rows(owner) == []
    assert skipped_task_rows(owner, []) == []
