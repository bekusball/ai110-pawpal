"""Tests for the scheduling behavior.

Every test here is marked `xfail(strict=True)` because Scheduler is still a
skeleton. Each one currently "passes" by raising NotImplementedError. Once you
implement a method, its test will start reporting XPASS, which strict mode turns
into a failure -- that is the cue to drop the xfail marker and tighten the
assertions to match the behavior you actually built.
"""

import pytest

from pawpal_system import Scheduler, Task


class TestSortTasks:
    @pytest.mark.xfail(raises=NotImplementedError, strict=True)
    def test_high_priority_comes_first(
        self, scheduler: Scheduler, tasks: list[Task]
    ) -> None:
        ordered = scheduler.sort_tasks(tasks)

        assert [task.priority for task in ordered] == ["high", "high", "low"]

    @pytest.mark.xfail(raises=NotImplementedError, strict=True)
    def test_keeps_every_task(self, scheduler: Scheduler, tasks: list[Task]) -> None:
        ordered = scheduler.sort_tasks(tasks)

        assert sorted(t.title for t in ordered) == sorted(t.title for t in tasks)

    @pytest.mark.xfail(raises=NotImplementedError, strict=True)
    def test_handles_empty_input(self, scheduler: Scheduler) -> None:
        assert scheduler.sort_tasks([]) == []


class TestBuildDailyPlan:
    @pytest.mark.xfail(raises=NotImplementedError, strict=True)
    def test_plan_fits_within_available_minutes(
        self, scheduler: Scheduler, tasks: list[Task]
    ) -> None:
        plan = scheduler.build_daily_plan(tasks, available_minutes=45)

        assert sum(task.duration_minutes for task in plan) <= 45

    @pytest.mark.xfail(raises=NotImplementedError, strict=True)
    def test_drops_low_priority_task_when_time_is_short(
        self, scheduler: Scheduler, tasks: list[Task], nail_trim: Task
    ) -> None:
        plan = scheduler.build_daily_plan(tasks, available_minutes=45)

        assert nail_trim not in plan

    @pytest.mark.xfail(raises=NotImplementedError, strict=True)
    def test_includes_everything_when_time_is_plentiful(
        self, scheduler: Scheduler, tasks: list[Task]
    ) -> None:
        plan = scheduler.build_daily_plan(tasks, available_minutes=480)

        assert len(plan) == len(tasks)

    @pytest.mark.xfail(raises=NotImplementedError, strict=True)
    def test_no_time_available_yields_empty_plan(
        self, scheduler: Scheduler, tasks: list[Task]
    ) -> None:
        assert scheduler.build_daily_plan(tasks, available_minutes=0) == []

    @pytest.mark.xfail(raises=NotImplementedError, strict=True)
    def test_skips_a_task_that_never_fits(self, scheduler: Scheduler) -> None:
        long_task = Task("Grooming appointment", 120, "high", "grooming")
        short_task = Task("Feeding", 10, "high", "food")

        plan = scheduler.build_daily_plan([long_task, short_task], available_minutes=30)

        assert plan == [short_task]


class TestExplainPlan:
    @pytest.mark.xfail(raises=NotImplementedError, strict=True)
    def test_one_explanation_per_task(
        self, scheduler: Scheduler, tasks: list[Task]
    ) -> None:
        explanations = scheduler.explain_plan(tasks)

        assert len(explanations) == len(tasks)

    @pytest.mark.xfail(raises=NotImplementedError, strict=True)
    def test_explanations_reference_task_titles(
        self, scheduler: Scheduler, morning_walk: Task
    ) -> None:
        explanations = scheduler.explain_plan([morning_walk])

        assert "Morning walk" in explanations[0]

    @pytest.mark.xfail(raises=NotImplementedError, strict=True)
    def test_empty_plan_has_no_explanations(self, scheduler: Scheduler) -> None:
        assert scheduler.explain_plan([]) == []
