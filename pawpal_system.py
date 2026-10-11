"""PawPal+ domain model and daily planner, matching diagrams/uml.mmd.

The model selects care tasks by priority and the owner's time budget. User
interfaces assign clock times and display the resulting plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
_FREQUENCIES = ("daily", "once")


@dataclass
class Task:
    """A care activity; frequency initially supports 'daily' and 'once'.

    completed records completion for the current planning day. Durations must
    be positive integers and priorities must be high, medium, or low.
    """

    title: str
    duration_minutes: int
    priority: str
    category: str
    completed: bool = False
    frequency: str = "daily"
    pet: Pet | None = field(default=None, repr=False, compare=False)
    id: str = field(default_factory=lambda: str(uuid4()), init=False)

    def __post_init__(self) -> None:
        if type(self.duration_minutes) is not int or self.duration_minutes <= 0:
            raise ValueError("duration_minutes must be a positive integer")
        if self.priority not in _PRIORITY_ORDER:
            raise ValueError("priority must be high, medium, or low")
        if self.frequency not in _FREQUENCIES:
            raise ValueError("frequency must be daily or once")

    def reset_for_new_day(self) -> None:
        """Reset daily completion; keep completed one-time tasks complete."""
        if self.frequency == "daily":
            self.completed = False

    def describe(self) -> str:
        """Return a human-readable one-line summary of this task."""
        pet_label = f"{self.pet.name} ({self.pet.species}): " if self.pet else ""
        return (
            f"{pet_label}{self.title} ({self.duration_minutes} min) "
            f"[priority: {self.priority}, category: {self.category}]"
        )


@dataclass
class Pet:
    """A pet that care tasks belong to."""

    name: str
    species: str
    tasks: list[Task] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid4()), init=False)

    def add_task(self, task: Task) -> None:
        """Set task.pet and attach it; reject tasks belonging to another pet."""
        if task.pet is not None and task.pet is not self:
            raise ValueError("task already belongs to another pet")
        task.pet = self
        if not any(existing is task for existing in self.tasks):
            self.tasks.append(task)


@dataclass
class Owner:
    """The pet owner, including a nonnegative time budget for today."""

    name: str
    available_minutes: int
    pets: list[Pet] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid4()), init=False)

    def __post_init__(self) -> None:
        if type(self.available_minutes) is not int or self.available_minutes < 0:
            raise ValueError("available_minutes must be a nonnegative integer")

    def add_pet(self, pet: Pet) -> None:
        """Attach a pet to this owner."""
        if not any(existing is pet for existing in self.pets):
            self.pets.append(pet)

    def get_all_tasks(self) -> list[Task]:
        """Return the tasks across all of this owner's pets."""
        return [task for pet in self.pets for task in pet.tasks]


@dataclass
class Scheduler:
    """Builds a daily plan from a set of tasks and the owner's time budget."""

    def sort_tasks(self, tasks: list[Task]) -> list[Task]:
        """Return a new list ordered by priority, preserving order for ties."""
        return sorted(tasks, key=lambda task: _PRIORITY_ORDER[task.priority])

    def build_daily_plan(self, owner: Owner) -> list[Task]:
        """Retrieve the owner's tasks and select incomplete tasks within their budget.

        Order high, medium, then low priority, keeping insertion order for ties.
        Skip tasks that do not fit and continue considering later tasks.
        """
        remaining_minutes = owner.available_minutes
        plan: list[Task] = []
        for task in self.sort_tasks(owner.get_all_tasks()):
            if not task.completed and task.duration_minutes <= remaining_minutes:
                plan.append(task)
                remaining_minutes -= task.duration_minutes
        return plan

    def explain_plan(self, plan: list[Task], available_minutes: int) -> list[str]:
        """Explain each task briefly using its priority and remaining budget."""
        remaining_minutes = available_minutes
        explanations: list[str] = []
        for task in plan:
            minutes_after_task = remaining_minutes - task.duration_minutes
            pet_label = f"{task.pet.name} / " if task.pet else ""
            explanations.append(
                f"{pet_label}{task.title}: {task.priority} priority; "
                f"{task.duration_minutes} min fits in {remaining_minutes} min; "
                f"{minutes_after_task} min left."
            )
            remaining_minutes = minutes_after_task
        return explanations
