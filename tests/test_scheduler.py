"""Scheduling tests for owner-based planning and budget-aware explanations."""

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
