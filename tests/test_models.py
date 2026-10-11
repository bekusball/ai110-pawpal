"""Tests for the Owner / Pet / Task data model."""

import pytest

from pawpal_system import Owner, Pet, Task


class TestTask:
    def test_defaults_to_not_completed(self, morning_walk: Task) -> None:
        assert morning_walk.completed is False

    def test_stores_its_fields(self, morning_walk: Task) -> None:
        assert morning_walk.title == "Morning walk"
        assert morning_walk.duration_minutes == 30
        assert morning_walk.priority == "high"
        assert morning_walk.category == "exercise"

    @pytest.mark.xfail(raises=NotImplementedError, strict=True)
    def test_describe_mentions_title_and_duration(self, morning_walk: Task) -> None:
        summary = morning_walk.describe()

        assert "Morning walk" in summary
        assert "30" in summary


class TestPet:
    def test_starts_with_no_tasks(self, pet: Pet) -> None:
        assert pet.tasks == []

    def test_task_lists_are_not_shared_between_pets(self) -> None:
        first = Pet(name="Mochi", species="dog")
        second = Pet(name="Biscuit", species="cat")

        first.tasks.append(Task("Feeding", 10, "high", "food"))

        assert second.tasks == []

    @pytest.mark.xfail(raises=NotImplementedError, strict=True)
    def test_add_task_appends_to_tasks(self, pet: Pet, morning_walk: Task) -> None:
        pet.add_task(morning_walk)

        assert pet.tasks == [morning_walk]


class TestOwner:
    def test_starts_with_no_pets(self, owner: Owner) -> None:
        assert owner.pets == []

    def test_pet_lists_are_not_shared_between_owners(self) -> None:
        first = Owner(name="Jordan", available_minutes=45)
        second = Owner(name="Sam", available_minutes=60)

        first.pets.append(Pet(name="Mochi", species="dog"))

        assert second.pets == []

    @pytest.mark.xfail(raises=NotImplementedError, strict=True)
    def test_add_pet_appends_to_pets(self, owner: Owner, pet: Pet) -> None:
        owner.add_pet(pet)

        assert owner.pets == [pet]
