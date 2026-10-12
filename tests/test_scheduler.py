"""Scheduling tests for owner-based planning and budget-aware explanations."""

from datetime import date, time, timedelta

import pytest

from pawpal_system import Owner, Pet, Scheduler, Task


class TestSortTasks:
    def test_priority_order_preserves_ties_and_input(self, scheduler: Scheduler) -> None:
        low = Task("Groom", 10, "low", "grooming")
        medium = Task("Play", 10, "medium", "enrichment")
        first = Task("Feed", 10, "high", "food")
        second = Task("Walk", 10, "high", "exercise")
        tasks = [low, first, medium, second]
        assert scheduler.sort_tasks(tasks) == [first, second, medium, low]
        assert tasks == [low, first, medium, second]

    def test_high_priority_comes_first(
        self, scheduler: Scheduler, tasks: list[Task]
    ) -> None:
        ordered = scheduler.sort_tasks(tasks)

        assert [task.priority for task in ordered] == ["high", "high", "low"]

    def test_keeps_every_task(self, scheduler: Scheduler, tasks: list[Task]) -> None:
        ordered = scheduler.sort_tasks(tasks)

        assert sorted(t.id for t in ordered) == sorted(t.id for t in tasks)

    def test_handles_empty_input(self, scheduler: Scheduler) -> None:
        assert scheduler.sort_tasks([]) == []

    def test_medium_priority_follows_high_and_precedes_low(
        self, scheduler: Scheduler, tasks: list[Task]
    ) -> None:
        tasks.append(Task("Enrichment", 10, "medium", "enrichment"))

        assert [task.priority for task in scheduler.sort_tasks(tasks)] == [
            "high", "high", "medium", "low"
        ]

    def test_preserves_insertion_order_for_ties(
        self, scheduler: Scheduler, morning_walk: Task, feeding: Task
    ) -> None:
        assert scheduler.sort_tasks([feeding, morning_walk]) == [feeding, morning_walk]

    def test_does_not_modify_input(
        self, scheduler: Scheduler, tasks: list[Task]
    ) -> None:
        original = tasks.copy()

        ordered = scheduler.sort_tasks(tasks)

        assert tasks == original
        assert ordered is not tasks


class TestBuildDailyPlan:
    @pytest.mark.parametrize("budget, titles", [
        (0, []),
        (1, []),
        (2, ["Brush"]),
        (4, ["Play"]),
        (6, ["Feed"]),
        (8, ["Walk"]),
        (10, ["Walk", "Brush"]),
        (12, ["Walk", "Play"]),
        (14, ["Walk", "Feed"]),
        (18, ["Walk", "Feed", "Play"]),
        (20, ["Walk", "Feed", "Play", "Brush"]),
    ])
    def test_budget_boundaries_across_pets(
        self, scheduler: Scheduler, budget: int, titles: list[str],
    ) -> None:
        today = date(2026, 10, 11)
        mochi = Pet("Mochi", "dog")
        luna = Pet("Luna", "cat")
        brush = Task("Brush", 2, "low", "grooming", due_date=today)
        walk = Task("Walk", 8, "high", "exercise", due_date=today)
        play = Task("Play", 4, "medium", "enrichment", due_date=today)
        feed = Task("Feed", 6, "high", "food", due_date=today)
        for pet, task in ((mochi, brush), (mochi, walk), (luna, play), (luna, feed)):
            pet.add_task(task)
        owner = Owner("Jordan", budget, pets=[mochi, luna])
        tasks_by_title = {task.title: task for task in owner.get_all_tasks()}

        plan = scheduler.build_daily_plan(owner, plan_date=today)

        assert plan == [tasks_by_title[title] for title in titles]
        assert all(task is tasks_by_title[task.title] for task in plan)
        assert sum(task.duration_minutes for task in plan) <= budget
        assert owner.available_minutes == budget
        assert mochi.tasks == [brush, walk]
        assert luna.tasks == [play, feed]
        assert all(not task.completed for task in owner.get_all_tasks())

    def test_replanning_uses_current_budget_and_returns_independent_lists(
        self, scheduler: Scheduler, owner_with_tasks: Owner,
        morning_walk: Task, feeding: Task,
    ) -> None:
        owner_with_tasks.available_minutes = 40
        first = scheduler.build_daily_plan(owner_with_tasks)
        owner_with_tasks.available_minutes = 10
        second = scheduler.build_daily_plan(owner_with_tasks)
        first.clear()
        owner_with_tasks.available_minutes = 40

        assert second == [feeding]
        assert scheduler.build_daily_plan(owner_with_tasks) == [morning_walk, feeding]
        assert len(owner_with_tasks.get_all_tasks()) == 3

    def test_overdue_dates_do_not_break_priority_ties(self, scheduler: Scheduler) -> None:
        today = date(2026, 10, 11)
        pet = Pet("Mochi", "dog")
        due = Task("Today", 10, "high", "care", due_date=today)
        overdue = Task("Overdue", 10, "high", "care", due_date=date(2026, 10, 1))
        for task in (due, overdue):
            pet.add_task(task)
        owner = Owner("Jordan", 10, pets=[pet])

        assert scheduler.build_daily_plan(owner, plan_date=today) == [due]

    def test_fixed_time_conflicts_do_not_change_budget_selection(
        self, scheduler: Scheduler,
    ) -> None:
        today = date(2026, 10, 11)
        pet = Pet("Mochi", "dog")
        low = Task("Brush", 10, "low", "care", due_date=today, fixed_start_time=time(8))
        high = Task("Feed", 10, "high", "food", due_date=today, fixed_start_time=time(8, 5))
        for task in (low, high):
            pet.add_task(task)
        owner = Owner("Jordan", 20, pets=[pet])

        assert scheduler.detect_conflicts(owner.get_all_tasks()) == [(low, high)]
        assert scheduler.build_daily_plan(owner, plan_date=today) == [high, low]

    def test_exact_budget_fit_is_included(
        self, scheduler: Scheduler, owner_with_tasks: Owner,
        morning_walk: Task, feeding: Task
    ) -> None:
        owner_with_tasks.available_minutes = 40

        assert scheduler.build_daily_plan(owner_with_tasks) == [morning_walk, feeding]

    def test_owner_without_pets_has_empty_plan(
        self, scheduler: Scheduler, owner: Owner
    ) -> None:
        assert scheduler.build_daily_plan(owner) == []

    def test_pet_without_tasks_has_empty_plan(
        self, scheduler: Scheduler, owner: Owner, pet: Pet
    ) -> None:
        owner.add_pet(pet)

        assert scheduler.build_daily_plan(owner) == []

    def test_plan_does_not_change_domain_state(
        self, scheduler: Scheduler, owner_with_tasks: Owner, tasks: list[Task]
    ) -> None:
        tasks[0].completed = True
        original_tasks = owner_with_tasks.get_all_tasks()
        original_completion = [task.completed for task in original_tasks]
        original_budget = owner_with_tasks.available_minutes

        first = scheduler.build_daily_plan(owner_with_tasks)
        second = scheduler.build_daily_plan(owner_with_tasks)

        assert first == second
        assert owner_with_tasks.get_all_tasks() == original_tasks
        assert [task.completed for task in original_tasks] == original_completion
        assert owner_with_tasks.available_minutes == original_budget

    def test_skips_completed_tasks(
        self, scheduler: Scheduler, owner_with_tasks: Owner, morning_walk: Task,
        feeding: Task, nail_trim: Task,
    ) -> None:
        morning_walk.completed = True
        assert scheduler.build_daily_plan(owner_with_tasks) == [feeding, nail_trim]

    def test_combines_tasks_across_pets(self, scheduler: Scheduler) -> None:
        owner = Owner("Jordan", 20)
        expected = []
        for name in ("Mochi", "Biscuit"):
            pet = Pet(name, "dog")
            task = Task("Feeding", 10, "high", "food")
            pet.add_task(task)
            owner.add_pet(pet)
            expected.append(task)
        plan = scheduler.build_daily_plan(owner)
        assert plan == expected
        assert [getattr(task.pet, 'name', None) for task in plan] == ["Mochi", "Biscuit"]

    def test_plan_fits_within_available_minutes(
        self, scheduler: Scheduler, owner_with_tasks: Owner
    ) -> None:
        plan = scheduler.build_daily_plan(owner_with_tasks)

        assert sum(task.duration_minutes for task in plan) <= 45

    def test_drops_low_priority_task_when_time_is_short(
        self, scheduler: Scheduler, owner_with_tasks: Owner, nail_trim: Task
    ) -> None:
        plan = scheduler.build_daily_plan(owner_with_tasks)

        assert nail_trim not in plan

    def test_includes_everything_when_time_is_plentiful(
        self, scheduler: Scheduler, tasks: list[Task], owner_with_tasks: Owner
    ) -> None:
        owner_with_tasks.available_minutes = 480
        plan = scheduler.build_daily_plan(owner_with_tasks)

        assert len(plan) == len(tasks)

    def test_no_time_available_yields_empty_plan(
        self, scheduler: Scheduler, owner_with_tasks: Owner
    ) -> None:
        owner_with_tasks.available_minutes = 0
        assert scheduler.build_daily_plan(owner_with_tasks) == []

    def test_skips_a_task_that_never_fits(self, scheduler: Scheduler) -> None:
        long_task = Task("Grooming appointment", 120, "high", "grooming")
        short_task = Task("Feeding", 10, "high", "food")

        pet = Pet("Mochi", "dog")
        pet.add_task(long_task)
        pet.add_task(short_task)
        owner = Owner("Jordan", 30, pets=[pet])
        plan = scheduler.build_daily_plan(owner)

        assert plan == [short_task]


class TestExplainPlan:
    def test_explanations_preserve_order_and_handle_unattached_tasks(
        self, scheduler: Scheduler,
    ) -> None:
        pet = Pet("Luna", "cat")
        feed = Task("Feed", 5, "high", "food")
        pet.add_task(feed)
        brush = Task("Brush", 10, "low", "grooming")
        plan = [feed, brush]

        assert scheduler.explain_plan(plan, 15) == [
            "Luna / Feed: high priority; 5 min fits in 15 min; 10 min left.",
            "Brush: low priority; 10 min fits in 10 min; 0 min left.",
        ]
        assert plan == [feed, brush]
        assert feed.pet is pet and brush.pet is None
        assert feed.completed is brush.completed is False

    def test_explanations_reference_pet_priority_duration_and_budget(
        self, scheduler: Scheduler, owner_with_tasks: Owner, morning_walk: Task
    ) -> None:
        explanation = scheduler.explain_plan([morning_walk], 45)[0]

        for detail in ("Mochi", "Morning walk", "high", "30 min", "45 min", "15 min"):
            assert detail in explanation

    def test_explanations_track_remaining_minutes(
        self, scheduler: Scheduler, morning_walk: Task, feeding: Task
    ) -> None:
        explanations = scheduler.explain_plan([morning_walk, feeding], 45)

        assert "fits in 15 min" in explanations[1]
        assert "5 min left" in explanations[1]

    def test_one_explanation_per_task(
        self, scheduler: Scheduler, tasks: list[Task]
    ) -> None:
        explanations = scheduler.explain_plan(tasks, available_minutes=60)

        assert len(explanations) == len(tasks)

    def test_explanations_reference_task_titles(
        self, scheduler: Scheduler, morning_walk: Task
    ) -> None:
        explanations = scheduler.explain_plan([morning_walk], available_minutes=45)

        assert "Morning walk" in explanations[0]

    def test_empty_plan_has_no_explanations(self, scheduler: Scheduler) -> None:
        assert scheduler.explain_plan([], available_minutes=45) == []


@pytest.fixture
def filter_candidates() -> list[Task]:
    tasks = []
    for name, completed in (
        (" Mochi ", False), ("Mochi", True), ("MOCHI", False), ("Luna", True),
    ):
        pet = Pet(name, "dog")
        task = Task("Feeding", 10, "high", "food", completed=completed)
        pet.add_task(task)
        tasks.append(task)
    tasks.append(Task("Unattached", 5, "low", "care"))
    return tasks


class TestFilterTasks:
    def test_pet_names_use_unicode_casefolding(self, scheduler: Scheduler) -> None:
        pet = Pet(" Straße ", "dog")
        task = Task("Walk", 10, "high", "exercise")
        pet.add_task(task)

        assert scheduler.filter_tasks([task], pet_name=" STRASSE ") == [task]
        assert scheduler.filter_tasks([task], pet_name="Strass") == []
        assert scheduler.filter_tasks([task], pet_name="   ") == []

    def test_filter_preserves_repeated_references_in_caller_order(
        self, scheduler: Scheduler, filter_candidates: list[Task],
    ) -> None:
        first, completed, second = filter_candidates[:3]
        candidates = [second, completed, first, second]

        result = scheduler.filter_tasks(candidates, completed=False, pet_name="Mochi")

        assert result == [second, first, second]
        assert result[0] is result[2] is second
        assert candidates == [second, completed, first, second]

    @pytest.mark.parametrize("completed, pet_name, indexes", [
        (None, None, [0, 1, 2, 3, 4]),
        (False, None, [0, 2, 4]),
        (True, None, [1, 3]),
        (None, " moCHI ", [0, 1, 2]),
        (False, "Mochi", [0, 2]),
        (True, "Mochi", [1]),
        (False, "Luna", []),
        (None, "Moch", []),
        (None, "Biscuit", []),
    ])
    def test_filters_combine_and_preserve_identity(
        self, scheduler: Scheduler, filter_candidates: list[Task],
        completed: bool | None, pet_name: str | None, indexes: list[int],
    ) -> None:
        result = scheduler.filter_tasks(
            filter_candidates, completed=completed, pet_name=pet_name,
        )

        assert [task.id for task in result] == [filter_candidates[i].id for i in indexes]
        assert all(task is filter_candidates[i] for task, i in zip(result, indexes))
        assert result is not filter_candidates

    def test_empty_input(self, scheduler: Scheduler) -> None:
        assert scheduler.filter_tasks([], completed=False, pet_name="Mochi") == []

    def test_filtering_does_not_change_tasks_or_the_source_list(
        self, scheduler: Scheduler, filter_candidates: list[Task],
    ) -> None:
        before = [(task.id, task.completed, task.pet) for task in filter_candidates]

        filtered = scheduler.filter_tasks(filter_candidates, completed=False)
        filtered.clear()

        assert [(task.id, task.completed, task.pet) for task in filter_candidates] == before


class TestCompleteTask:
    def test_completion_on_a_later_pet_is_isolated_to_its_occurrence(
        self, scheduler: Scheduler,
    ) -> None:
        today = date(2026, 10, 11)
        pets = [Pet("Mochi", "dog"), Pet("Mochi", "dog"), Pet("Mochi", "dog")]
        tasks = [Task("Feed", 10, "high", "food", due_date=today) for _ in pets]
        for pet, task in zip(pets, tasks):
            pet.add_task(task)
        owner = Owner("Jordan", 30, pets=pets[:2])
        other_owner = Owner("Sam", 30, pets=[pets[2]])

        successor = scheduler.mark_task_complete(owner, tasks[1].id, today=today)

        assert successor is not None and successor.pet is pets[1]
        assert pets[0].tasks == [tasks[0]]
        assert pets[1].tasks == [tasks[1], successor]
        assert other_owner.get_all_tasks() == [tasks[2]]
        assert [task.completed for task in tasks] == [False, True, False]
        assert owner.available_minutes == other_owner.available_minutes == 30

    def test_successor_details_are_independent_of_the_completed_occurrence(
        self, scheduler: Scheduler, owner_with_tasks: Owner, feeding: Task,
    ) -> None:
        successor = scheduler.mark_task_complete(
            owner_with_tasks, feeding.id, today=date(2026, 10, 11),
        )
        assert successor is not None
        successor.title = "Evening feed"
        successor.duration_minutes = 5
        successor.priority = "medium"
        successor.category = "care"
        successor.fixed_start_time = time(18)

        assert feeding.title == "Feeding"
        assert feeding.duration_minutes == 10
        assert feeding.priority == "high"
        assert feeding.category == "food"
        assert feeding.fixed_start_time is None
        assert feeding.completed is True and successor.completed is False

    def test_daily_completion_retains_history_and_copies_details(
        self, scheduler: Scheduler, owner_with_tasks: Owner, morning_walk: Task,
    ) -> None:
        today = date(2026, 10, 11)
        morning_walk.due_date = date(2026, 10, 1)
        morning_walk.fixed_start_time = time(8)
        pet = morning_walk.pet
        original_tasks = owner_with_tasks.get_all_tasks()
        budget = owner_with_tasks.available_minutes

        successor = scheduler.mark_task_complete(owner_with_tasks, morning_walk.id, today=today)

        assert successor is not None
        assert successor is not morning_walk
        assert successor.id not in {task.id for task in original_tasks}
        assert successor.pet is pet
        assert pet is not None and pet.tasks[-1] is successor
        assert all(task in owner_with_tasks.get_all_tasks() for task in original_tasks)
        assert morning_walk.completed is True
        assert morning_walk.due_date == date(2026, 10, 1)
        assert successor.completed is False
        assert successor.due_date == date(2026, 10, 12)
        assert (
            successor.title, successor.duration_minutes, successor.priority,
            successor.category, successor.frequency, successor.fixed_start_time,
        ) == ("Morning walk", 30, "high", "exercise", "daily", time(8))
        assert owner_with_tasks.available_minutes == budget

    @pytest.mark.parametrize("today, tomorrow", [
        (date(2026, 1, 31), date(2026, 2, 1)),
        (date(2026, 12, 31), date(2027, 1, 1)),
        (date(2028, 2, 28), date(2028, 2, 29)),
        (date(2028, 2, 29), date(2028, 3, 1)),
        (date(2026, 2, 28), date(2026, 3, 1)),
    ])
    def test_successor_date_rollover(
        self, scheduler: Scheduler, owner_with_tasks: Owner, feeding: Task,
        today: date, tomorrow: date,
    ) -> None:
        successor = scheduler.mark_task_complete(owner_with_tasks, feeding.id, today=today)

        assert successor is not None and successor.due_date == tomorrow

    def test_completion_defaults_to_today(
        self, scheduler: Scheduler, owner_with_tasks: Owner, feeding: Task,
    ) -> None:
        successor = scheduler.mark_task_complete(owner_with_tasks, feeding.id)

        assert successor is not None
        assert successor.due_date == date.today() + timedelta(days=1)

    def test_once_completion_has_no_successor(
        self, scheduler: Scheduler, owner_with_tasks: Owner, nail_trim: Task,
    ) -> None:
        nail_trim.frequency = "once"
        original_tasks = owner_with_tasks.get_all_tasks()

        assert scheduler.mark_task_complete(owner_with_tasks, nail_trim.id) is None

        assert nail_trim.completed is True
        assert owner_with_tasks.get_all_tasks() == original_tasks

    @pytest.mark.parametrize("frequency", ["daily", "once"])
    def test_repeated_completion_is_a_no_op(
        self, scheduler: Scheduler, owner_with_tasks: Owner,
        feeding: Task, frequency: str,
    ) -> None:
        feeding.frequency = frequency
        scheduler.mark_task_complete(owner_with_tasks, feeding.id)
        after_first = owner_with_tasks.get_all_tasks()

        assert scheduler.mark_task_complete(owner_with_tasks, feeding.id) is None

        assert owner_with_tasks.get_all_tasks() == after_first
        assert feeding.completed is True

    def test_ids_distinguish_matching_tasks_and_successors_can_recur(
        self, scheduler: Scheduler, owner: Owner, pet: Pet,
    ) -> None:
        first = Task("Feeding", 10, "high", "food")
        second = Task("Feeding", 10, "high", "food")
        pet.add_task(first)
        pet.add_task(second)
        owner.add_pet(pet)

        tomorrow = scheduler.mark_task_complete(owner, second.id, today=date(2026, 10, 11))
        assert tomorrow is not None
        following = scheduler.mark_task_complete(owner, tomorrow.id, today=date(2026, 10, 12))

        assert first.completed is False
        assert second.completed is tomorrow.completed is True
        assert following is not None and following.completed is False
        assert following.due_date == date(2026, 10, 13)
        assert pet.tasks == [first, second, tomorrow, following]
        assert len({task.id for task in pet.tasks}) == 4

    def test_unknown_or_other_owner_id_does_not_change_state(
        self, scheduler: Scheduler, owner_with_tasks: Owner,
    ) -> None:
        other_pet = Pet("Luna", "cat")
        other_task = Task("Feeding", 5, "high", "food")
        other_pet.add_task(other_task)
        other_owner = Owner("Sam", 30, pets=[other_pet])
        original_tasks = owner_with_tasks.get_all_tasks()

        for task_id in ("missing", other_task.id):
            with pytest.raises(ValueError, match="task_id"):
                scheduler.mark_task_complete(owner_with_tasks, task_id)

        assert owner_with_tasks.get_all_tasks() == original_tasks
        assert all(not task.completed for task in original_tasks)
        assert other_owner.get_all_tasks() == [other_task]
        assert other_task.completed is False


class TestDatedPlanning:
    def test_recurring_lifecycle_keeps_history_and_plans_only_due_occurrences(
        self, scheduler: Scheduler,
    ) -> None:
        today = date(2026, 12, 30)
        pet = Pet("Mochi", "dog")
        daily = Task("Feed", 10, "high", "food", due_date=today, fixed_start_time=time(8))
        once = Task("Nail trim", 5, "low", "grooming", frequency="once", due_date=today)
        for task in (daily, once):
            pet.add_task(task)
        owner = Owner("Jordan", 15, pets=[pet])
        assert scheduler.build_daily_plan(owner, plan_date=today) == [daily, once]
        assert scheduler.mark_task_complete(owner, once.id, today=today) is None
        history = [daily, once]
        current = daily

        for offset in range(3):
            completion_date = today + timedelta(days=offset)
            assert scheduler.build_daily_plan(owner, plan_date=completion_date) == [current]
            successor = scheduler.mark_task_complete(owner, current.id, today=completion_date)
            assert successor is not None
            if offset:
                history.append(current)
            assert scheduler.mark_task_complete(owner, current.id, today=completion_date) is None
            assert scheduler.filter_tasks(owner.get_all_tasks(), completed=True) == history
            assert scheduler.filter_tasks(owner.get_all_tasks(), completed=False) == [successor]
            assert scheduler.build_daily_plan(owner, plan_date=completion_date) == []
            assert successor.due_date == completion_date + timedelta(days=1)
            assert successor.pet is pet
            assert successor.fixed_start_time == time(8)
            current = successor

        assert scheduler.build_daily_plan(owner, plan_date=date(2027, 1, 2)) == [current]
        assert len(pet.tasks) == len({task.id for task in pet.tasks}) == 5
        assert all(task.completed for task in history)
        assert owner.available_minutes == 15

    def test_daily_successor_is_excluded_today_and_included_tomorrow(
        self, scheduler: Scheduler, owner: Owner, pet: Pet, feeding: Task,
    ) -> None:
        pet.add_task(feeding)
        owner.add_pet(pet)
        today = date(2026, 10, 11)
        successor = scheduler.mark_task_complete(owner, feeding.id, today=today)

        assert scheduler.build_daily_plan(owner, plan_date=today) == []
        assert scheduler.build_daily_plan(owner, plan_date=today + timedelta(days=1)) == [successor]
        assert scheduler.build_daily_plan(owner, plan_date=today + timedelta(days=1)) == [successor]
        assert pet.tasks == [feeding, successor]
        assert feeding.completed is True
        assert successor is not None and successor.completed is False

    def test_date_filter_keeps_overdue_tasks_priority_and_budget_rules(
        self, scheduler: Scheduler, owner: Owner, pet: Pet,
    ) -> None:
        today = date(2026, 10, 11)
        due = Task("Today", 5, "low", "care", due_date=today)
        overdue = Task("Overdue", 10, "medium", "care", due_date=today - timedelta(days=1))
        future = Task("Future", 10, "high", "care", due_date=today + timedelta(days=1))
        oversized = Task("Too long", 30, "high", "care", due_date=today)
        completed = Task("Done", 5, "high", "care", completed=True, due_date=today)
        for task in (due, future, overdue, oversized, completed):
            pet.add_task(task)
        owner.add_pet(pet)
        owner.available_minutes = 15

        assert scheduler.build_daily_plan(owner, plan_date=today) == [overdue, due]
        assert owner.available_minutes == 15
        assert pet.tasks == [due, future, overdue, oversized, completed]

    def test_default_planning_date_excludes_future_tasks(
        self, scheduler: Scheduler, owner: Owner, pet: Pet,
    ) -> None:
        future = Task("Tomorrow", 5, "high", "care", due_date=date.today() + timedelta(days=1))
        pet.add_task(future)
        owner.add_pet(pet)

        assert scheduler.build_daily_plan(owner) == []


class TestDetectConflicts:
    @pytest.mark.parametrize("start_date, next_date", [
        (date(2026, 10, 31), date(2026, 11, 1)),
        (date(2026, 12, 31), date(2027, 1, 1)),
        (date(2028, 2, 28), date(2028, 2, 29)),
    ])
    def test_midnight_conflicts_across_calendar_boundaries(
        self, scheduler: Scheduler, start_date: date, next_date: date,
    ) -> None:
        late = Task("Late care", 20, "low", "care", due_date=start_date, fixed_start_time=time(23, 50))
        early = Task("Early care", 5, "high", "care", due_date=next_date, fixed_start_time=time(0, 5))

        assert scheduler.detect_conflicts([late, early]) == [(late, early)]
        assert scheduler.detect_conflicts([early, late]) == [(early, late)]

    def test_long_interval_contains_a_task_two_days_later(self, scheduler: Scheduler) -> None:
        long = Task(
            "Long care", 1500, "low", "care",
            due_date=date(2026, 10, 11), fixed_start_time=time(23, 30),
        )
        inside = Task(
            "Feeding", 10, "high", "food",
            due_date=date(2026, 10, 13), fixed_start_time=time(0, 15),
        )
        adjacent = Task(
            "Walk", 10, "high", "exercise",
            due_date=date(2026, 10, 13), fixed_start_time=time(0, 30),
        )

        assert scheduler.detect_conflicts([long, inside, adjacent]) == [(long, inside)]

    def test_future_occurrences_are_reported_and_completion_removes_a_conflict(
        self, scheduler: Scheduler,
    ) -> None:
        today = date(2026, 10, 11)
        tomorrow = today + timedelta(days=1)
        pet = Pet("Mochi", "dog")
        first = Task("Walk", 30, "high", "care", due_date=tomorrow, fixed_start_time=time(8))
        second = Task("Feed", 10, "high", "care", due_date=tomorrow, fixed_start_time=time(8, 5), frequency="once")
        for task in (first, second):
            pet.add_task(task)
        owner = Owner("Jordan", 40, pets=[pet])

        assert scheduler.build_daily_plan(owner, plan_date=today) == []
        assert scheduler.detect_conflicts(owner.get_all_tasks()) == [(first, second)]
        assert scheduler.mark_task_complete(owner, second.id, today=tomorrow) is None
        assert scheduler.detect_conflicts(owner.get_all_tasks()) == []
        assert scheduler.build_daily_plan(owner, plan_date=tomorrow) == [first]

    def test_repeating_the_same_task_cannot_create_a_self_conflict(
        self, scheduler: Scheduler,
    ) -> None:
        task = Task("Walk", 30, "high", "care", fixed_start_time=time(8))

        assert scheduler.detect_conflicts([task, task, task]) == []

    @pytest.mark.parametrize("offset, start, duration, overlaps", [
        (0, time(8, 15), 20, True),
        (0, time(8, 5), 10, True),
        (0, time(7, 50), 20, True),
        (0, time(8), 30, True),
        (0, time(8, 30), 10, False),
        (0, time(7, 50), 10, False),
        (0, time(9), 10, False),
        (1, time(8, 15), 20, False),
    ])
    def test_intervals_across_an_owners_pets(
        self, scheduler: Scheduler, owner: Owner,
        offset: int, start: time, duration: int, overlaps: bool,
    ) -> None:
        today = date(2026, 10, 11)
        first = Task("Walk", 30, "high", "exercise", due_date=today, fixed_start_time=time(8))
        second = Task(
            "Walk", duration, "high", "exercise",
            due_date=today + timedelta(days=offset), fixed_start_time=start,
        )
        for name, task in (("Mochi", first), ("Biscuit", second)):
            pet = Pet(name, "dog")
            pet.add_task(task)
            owner.add_pet(pet)
        original_plan = scheduler.build_daily_plan(owner, plan_date=today)

        assert scheduler.detect_conflicts(owner.get_all_tasks()) == (
            [(first, second)] if overlaps else []
        )

        assert owner.get_all_tasks() == [first, second]
        assert first.completed is second.completed is False
        assert scheduler.build_daily_plan(owner, plan_date=today) == original_plan
        assert owner.available_minutes == 45

    @pytest.mark.parametrize("next_start, overlaps", [(time(0, 5), True), (time(0, 10), False)])
    def test_midnight_crossing(self, scheduler: Scheduler, next_start: time, overlaps: bool) -> None:
        first = Task(
            "Late walk", 20, "high", "exercise",
            due_date=date(2026, 10, 11), fixed_start_time=time(23, 50),
        )
        second = Task(
            "Feeding", 10, "high", "food",
            due_date=date(2026, 10, 12), fixed_start_time=next_start,
        )

        assert scheduler.detect_conflicts([first, second]) == ([(first, second)] if overlaps else [])

    def test_multiple_conflicts_are_unique_and_preserve_input_order(self, scheduler: Scheduler) -> None:
        tasks = [
            Task("Care", 30, "high", "care", fixed_start_time=start)
            for start in (time(8), time(8, 5), time(8, 10))
        ]
        first, second, third = tasks
        candidates = [first, second, third, first]

        assert scheduler.detect_conflicts(candidates) == [
            (first, second), (first, third), (second, third),
        ]
        assert candidates == [first, second, third, first]

    def test_completed_and_flexible_tasks_do_not_conflict(self, scheduler: Scheduler) -> None:
        fixed = Task("Walk", 30, "high", "exercise", fixed_start_time=time(8))
        completed = Task("Done", 30, "high", "care", completed=True, fixed_start_time=time(8))
        flexible = Task("Any time", 30, "high", "care")

        assert scheduler.detect_conflicts([fixed, completed, flexible]) == []
        assert scheduler.detect_conflicts([fixed]) == []
        assert scheduler.detect_conflicts([]) == []
