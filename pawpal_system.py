"""PawPal+ domain model.

Class skeleton generated from diagrams/uml_draft.mmd. Attributes and method
signatures are in place; the scheduling behavior is not implemented yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class Task:
    """A care activity; frequency initially supports 'daily' and 'once'.

    completed records completion for the current planning day. Durations must
    be positive and priorities must be high, medium, or low when implemented.
    """

    title: str
    duration_minutes: int
    priority: str
    category: str
    completed: bool = False
    frequency: str = "daily"
    pet: Pet | None = field(default=None, repr=False, compare=False)
    id: str = field(default_factory=lambda: str(uuid4()), init=False)

    def reset_for_new_day(self) -> None:
        """Reset daily completion; keep completed one-time tasks complete."""
        raise NotImplementedError

    def describe(self) -> str:
        """Return a human-readable one-line summary of this task."""
        raise NotImplementedError


@dataclass
class Pet:
    """A pet that care tasks belong to."""

    name: str
    species: str
    tasks: list[Task] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid4()), init=False)

    def add_task(self, task: Task) -> None:
        """Set task.pet and attach it; reject tasks belonging to another pet."""
        raise NotImplementedError


@dataclass
class Owner:
    """The pet owner, including a nonnegative time budget for today."""

    name: str
    available_minutes: int
    pets: list[Pet] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid4()), init=False)

    def add_pet(self, pet: Pet) -> None:
        """Attach a pet to this owner."""
        raise NotImplementedError

    def get_all_tasks(self) -> list[Task]:
        """Return the tasks across all of this owner's pets."""
        raise NotImplementedError


@dataclass
class Scheduler:
    """Builds a daily plan from a set of tasks and the owner's time budget."""

    def sort_tasks(self, tasks: list[Task]) -> list[Task]:
        """Return the tasks ordered by scheduling preference (e.g. priority)."""
        raise NotImplementedError

    def build_daily_plan(self, owner: Owner) -> list[Task]:
        """Retrieve the owner's tasks and select incomplete tasks within their budget.

        Order high, medium, then low priority, keeping insertion order for ties.
        Skip tasks that do not fit and continue considering later tasks.
        """
        raise NotImplementedError

    def explain_plan(self, plan: list[Task], available_minutes: int) -> list[str]:
        """Explain each selected task using its priority and the time budget."""
        raise NotImplementedError
