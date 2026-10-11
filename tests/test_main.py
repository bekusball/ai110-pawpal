"""Check the demo data, printed schedule, and guarded CLI entrypoint."""

from datetime import date, timedelta
from pathlib import Path
import re
import subprocess
import sys

import pytest

import main as demo
from pawpal_system import Scheduler


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_demo_has_two_dogs_one_cat_and_one_to_three_tasks_each() -> None:
    owner = demo.build_demo_owner()

    assert owner.name == "Jordan"
    assert [pet.name for pet in owner.pets] == ["Mochi", "Biscuit", "Luna"]
    assert [pet.species for pet in owner.pets] == ["dog", "dog", "cat"]
    assert [len(pet.tasks) for pet in owner.pets] == [3, 2, 1]
    assert all(task.pet is pet for pet in owner.pets for task in pet.tasks)


def test_default_cli_prints_expected_schedule_and_totals() -> None:
    result = subprocess.run(
        [sys.executable, "main.py"], cwd=PROJECT_ROOT,
        capture_output=True, text=True, check=True,
    )
    output = result.stdout
    rows = [
        re.split(r" {2,}", line.strip()) for line in output.splitlines()
        if line[:2].isdigit()
    ]

    assert rows == [
        ["08:00-08:30", "Mochi", "Morning walk", "30", "HIGH"],
        ["08:30-08:40", "Mochi", "Feeding", "10", "HIGH"],
        ["08:40-09:00", "Biscuit", "Morning walk", "20", "HIGH"],
        ["09:00-09:05", "Luna", "Feeding", "5", "HIGH"],
        ["09:05-09:15", "Biscuit", "Enrichment", "10", "MEDIUM"],
        ["09:15-09:30", "Mochi", "Brushing", "15", "LOW"],
    ]
    assert f"Jordan's schedule | {date.today().isoformat()} | Budget: 90 min" in output
    assert "6 tasks | Used: 90 min | Remaining: 0 min" in output
    assert "Why these tasks:" in output
    assert output.count("  - ") == 6
    assert "Mochi / Morning walk: high priority; 30 min fits in 90 min; 60 min left." in output
    assert "Mochi / Brushing: low priority; 15 min fits in 15 min; 0 min left." in output
    assert "Skipped: none" in output
    assert result.stderr == ""


def test_constrained_plan_skips_walk_but_continues_to_shorter_tasks() -> None:
    owner = demo.build_demo_owner(available_minutes=55)

    plan = Scheduler().build_daily_plan(owner)

    assert [(task.pet.name, task.title) for task in plan] == [
        ("Mochi", "Morning walk"), ("Mochi", "Feeding"),
        ("Luna", "Feeding"), ("Biscuit", "Enrichment"),
    ]
    assert sum(task.duration_minutes for task in plan) == 55


def test_constrained_output_identifies_skipped_tasks(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    original_builder = demo.build_demo_owner
    monkeypatch.setattr(
        demo, "build_demo_owner",
        lambda available_minutes=90: original_builder(available_minutes=55),
    )

    demo.main()
    output = capsys.readouterr().out
    schedule, skipped = output.split("Skipped (insufficient time):")

    assert "Budget: 55 min" in output
    assert "4 tasks | Used: 55 min | Remaining: 0 min" in output
    assert "Why these tasks:" in schedule
    assert schedule.count("  - ") == 4
    assert "Biscuit / Enrichment: medium priority; 10 min fits in 10 min; 0 min left." in schedule
    assert [
        re.split(r" {2,}", line.strip()) for line in schedule.splitlines()
        if line[:2].isdigit()
    ] == [
        ["08:00-08:30", "Mochi", "Morning walk", "30", "HIGH"],
        ["08:30-08:40", "Mochi", "Feeding", "10", "HIGH"],
        ["08:40-08:45", "Luna", "Feeding", "5", "HIGH"],
        ["08:45-08:55", "Biscuit", "Enrichment", "10", "MEDIUM"],
    ]
    assert [
        re.split(r" {2,}", line.strip()) for line in skipped.strip().splitlines()[2:]
    ] == [
        ["Biscuit", "Morning walk", "20"],
        ["Mochi", "Brushing", "15"],
    ]


def test_importing_main_is_silent() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import main"], cwd=PROJECT_ROOT,
        capture_output=True, text=True, check=True,
    )

    assert result.stdout == ""
    assert result.stderr == ""


def test_algorithms_cli_shows_filters_recurrence_and_cross_pet_conflicts() -> None:
    result = subprocess.run(
        [sys.executable, "main.py", "--algorithms"], cwd=PROJECT_ROOT,
        capture_output=True, text=True, check=True,
    )
    output = result.stdout
    today = date.today()
    tomorrow = today + timedelta(days=1)

    assert f"PawPal+ algorithms | {today.isoformat()}" in output
    assert f"Completed Mochi / Feeding; new incomplete daily occurrence due {tomorrow.isoformat()}." in output
    assert "Completed Mochi / Nail trim; no successor (once)." in output
    incomplete, completed = output.split("Incomplete tasks for Mochi (status + pet filter):")[1].split(
        "Completed tasks for Mochi (status + pet filter):",
    )
    incomplete_rows = [
        re.split(r" {2,}", line.strip()) for line in incomplete.splitlines()
        if line.startswith("Mochi")
    ]
    assert incomplete_rows == [
        ["Mochi", "Morning walk", "daily", today.isoformat(), "no"],
        ["Mochi", "Brushing", "daily", today.isoformat(), "no"],
        ["Mochi", "Feeding", "daily", tomorrow.isoformat(), "no"],
    ]
    completed_rows = [
        re.split(r" {2,}", line.strip()) for line in completed.splitlines()
        if line.startswith("Mochi")
    ]
    assert completed_rows == [
        ["Mochi", "Feeding", "daily", today.isoformat(), "yes"],
        ["Mochi", "Nail trim", "once", today.isoformat(), "yes"],
    ]
    assert f"Daily successor in the plan:\n  {today.isoformat()}: no\n  {tomorrow.isoformat()}: yes" in output
    assert (
        f"Conflict: Mochi / Morning walk ({today.isoformat()} 08:00 to {today.isoformat()} 08:30) "
        f"overlaps Biscuit / Morning walk ({today.isoformat()} 08:15 to {today.isoformat()} 08:35)"
    ) in output
    assert output.count("Conflict:") == 1
    assert result.stderr == ""


def test_cli_help_describes_the_algorithms_flag() -> None:
    result = subprocess.run(
        [sys.executable, "main.py", "--help"], cwd=PROJECT_ROOT,
        capture_output=True, text=True, check=True,
    )

    assert "--algorithms" in result.stdout
    assert "filtering, completion, recurrence, and conflicts" in result.stdout
    assert result.stderr == ""
