"""Tests for the Owner / Pet / Task data model."""

from datetime import date, datetime, time, timezone

import pytest

from pawpal_system import Owner, Pet, Task


class TestTask:
    def test_defaults_to_daily_and_unattached(self, morning_walk: Task) -> None:
        assert morning_walk.frequency == "daily"
        assert morning_walk.pet is None

    def test_defaults_to_today_without_a_fixed_start(self, morning_walk: Task) -> None:
        assert morning_walk.due_date == date.today()
        assert morning_walk.fixed_start_time is None

    def test_new_fields_preserve_existing_positional_arguments(self, pet: Pet) -> None:
        task = Task(
            "Feeding", 10, "high", "food", False, "once", pet,
            due_date=date(2026, 10, 12), fixed_start_time=time(8),
        )

        assert task.pet is pet
        assert task.frequency == "once"
        assert task.completed is False
        assert task.due_date == date(2026, 10, 12)
        assert task.fixed_start_time == time(8)

    @pytest.mark.parametrize("duration", [0, -1, 1.5, "10", True, False, None])
    def test_rejects_invalid_duration(self, duration: object) -> None:
        with pytest.raises(ValueError, match="duration_minutes"):
            Task("Feeding", duration, "high", "food") # pyright: ignore[reportArgumentType]

    @pytest.mark.parametrize("priority", ["urgent", "HIGH", "", None])
    def test_rejects_invalid_priority(self, priority: str) -> None:
        with pytest.raises(ValueError, match="priority"):
            Task("Feeding", 10, priority, "food")

    @pytest.mark.parametrize("frequency", ["weekly", "", None])
    def test_rejects_invalid_frequency(self, frequency: str) -> None:
        with pytest.raises(ValueError, match="frequency"):
            Task("Feeding", 10, "high", "food", frequency=frequency)

    @pytest.mark.parametrize("due_date", [None, "2026-10-11", datetime(2026, 10, 11)])
    def test_rejects_invalid_due_date(self, due_date: object) -> None:
        with pytest.raises(ValueError, match="due_date"):
            Task("Feeding", 10, "high", "food", due_date=due_date) # pyright: ignore[reportArgumentType]

    @pytest.mark.parametrize(
        "fixed_start", ["08:00", datetime(2026, 10, 11, 8), time(8, tzinfo=timezone.utc)],
    )
    def test_rejects_invalid_or_timezone_aware_start(self, fixed_start: object) -> None:
        with pytest.raises(ValueError, match="fixed_start_time"):
            Task("Feeding", 10, "high", "food", fixed_start_time=fixed_start) # pyright: ignore[reportArgumentType]

    def test_defaults_to_not_completed(self, morning_walk: Task) -> None:
        assert morning_walk.completed is False

    def test_stores_its_fields(self, morning_walk: Task) -> None:
        assert morning_walk.title == "Morning walk"
        assert morning_walk.duration_minutes == 30
        assert morning_walk.priority == "high"
        assert morning_walk.category == "exercise"

    def test_describe_mentions_title_and_duration(self, morning_walk: Task) -> None:
        summary = morning_walk.describe()

        assert "Morning walk" in summary
        assert "30" in summary

    def test_describe_mentions_attached_pet(
        self, pet: Pet, morning_walk: Task
    ) -> None:
        pet.add_task(morning_walk)

        assert "Mochi (dog)" in morning_walk.describe()


class TestPet:
    def test_cannot_attach_task_to_another_pet(self, pet: Pet, morning_walk: Task) -> None:
        pet.add_task(morning_walk)
        other = Pet("Biscuit", "cat")
        with pytest.raises(ValueError):
            other.add_task(morning_walk)
        assert morning_walk.pet is pet
        assert other.tasks == []
        assert pet.tasks == [morning_walk]

    def test_adding_same_task_twice_is_a_no_op(
        self, pet: Pet, morning_walk: Task
    ) -> None:
        pet.add_task(morning_walk)
        pet.add_task(morning_walk)

        assert pet.tasks == [morning_walk]

    def test_distinct_tasks_with_matching_fields_are_both_attached(
        self, pet: Pet
    ) -> None:
        first = Task("Feeding", 10, "high", "food")
        second = Task("Feeding", 10, "high", "food")
        pet.add_task(first)
        pet.add_task(second)

        assert pet.tasks == [first, second]

    def test_starts_with_no_tasks(self, pet: Pet) -> None:
        assert pet.tasks == []

    def test_task_lists_are_not_shared_between_pets(self) -> None:
        first = Pet(name="Mochi", species="dog")
        second = Pet(name="Biscuit", species="cat")

        first.add_task(Task("Feeding", 10, "high", "food"))

        assert second.tasks == []

    def test_add_task_appends_to_tasks(self, pet: Pet, morning_walk: Task) -> None:
        pet.add_task(morning_walk)

        assert pet.tasks == [morning_walk]
        assert morning_walk.pet is pet


class TestOwner:
    def test_get_all_tasks(self, owner_with_tasks: Owner, tasks: list[Task]) -> None:
        assert owner_with_tasks.get_all_tasks() == tasks

    def test_ids_are_unique(self) -> None:
        models = [Owner("Jordan", 45), Owner("Jordan", 45), Pet("Mochi", "dog"),
                  Pet("Mochi", "dog"), Task("Feed", 10, "high", "food"),
                  Task("Feed", 10, "high", "food")]
        assert len({model.id for model in models}) == len(models)

    def test_starts_with_no_pets(self, owner: Owner) -> None:
        assert owner.pets == []

    def test_pet_lists_are_not_shared_between_owners(self) -> None:
        first = Owner(name="Jordan", available_minutes=45)
        second = Owner(name="Sam", available_minutes=60)

        first.add_pet(Pet(name="Mochi", species="dog"))

        assert second.pets == []

    def test_add_pet_appends_to_pets(self, owner: Owner, pet: Pet) -> None:
        owner.add_pet(pet)

        assert owner.pets == [pet]

    def test_adding_same_pet_twice_is_a_no_op(self, owner: Owner, pet: Pet) -> None:
        owner.add_pet(pet)
        owner.add_pet(pet)

    @pytest.mark.parametrize("minutes", [-1, 1.5, "45", True, False, None])
    def test_rejects_invalid_budget(self, minutes: object) -> None:
        with pytest.raises(ValueError, match="available_minutes"):
            Owner("Jordan", minutes) # pyright: ignore[reportArgumentType]

    def test_accepts_zero_budget(self) -> None:
        assert Owner("Jordan", 0).available_minutes == 0

    def test_distinct_pets_with_matching_names_are_both_attached(self, owner: Owner) -> None:
        first = Pet("Mochi", "dog")
        second = Pet("Mochi", "dog")
        owner.add_pet(first)
        owner.add_pet(second)
        owner.add_pet(first)

        assert owner.pets == [first, second]
        assert owner.pets[0] is first and owner.pets[1] is second

    def test_get_all_tasks_preserves_pet_and_task_order(
        self, owner: Owner, pet: Pet, morning_walk: Task, feeding: Task, nail_trim: Task
    ) -> None:
        other_pet = Pet("Luna", "cat")
        pet.add_task(nail_trim)
        pet.add_task(morning_walk)
        other_pet.add_task(feeding)
        owner.add_pet(pet)
        owner.add_pet(other_pet)

        combined = owner.get_all_tasks()

        assert combined == [nail_trim, morning_walk, feeding]
        combined.clear()
        assert pet.tasks == [nail_trim, morning_walk]
        assert other_pet.tasks == [feeding]
