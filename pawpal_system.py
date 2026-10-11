"""PawPal+ domain model.

Class skeleton generated from diagrams/uml_draft.mmd. Attributes and method
signatures are in place; the scheduling behavior is not implemented yet.
"""

from dataclasses import dataclass, field


@dataclass
class Task:
    """A single pet care task (walk, feeding, meds, enrichment, grooming...)."""

    title: str
    duration_minutes: int
    priority: str
    category: str
    completed: bool = False

    def describe(self) -> str:
        """Return a human-readable one-line summary of this task."""
        raise NotImplementedError


@dataclass
class Pet:
    """A pet that care tasks belong to."""

    name: str
    species: str
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Attach a task to this pet."""
        raise NotImplementedError


@dataclass
class Owner:
    """The pet owner, including how much time they have available today."""

    name: str
    available_minutes: int
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Attach a pet to this owner."""
        raise NotImplementedError


@dataclass
class Scheduler:
    """Builds a daily plan from a set of tasks and the owner's time budget."""

    def sort_tasks(self, tasks: list[Task]) -> list[Task]:
        """Return the tasks ordered by scheduling preference (e.g. priority)."""
        raise NotImplementedError

    def build_daily_plan(self, tasks: list[Task], available_minutes: int) -> list[Task]:
        """Select the tasks that fit within the available time, in plan order."""
        raise NotImplementedError

    def explain_plan(self, plan: list[Task]) -> list[str]:
        """Return one explanation line per task describing why it was chosen."""
        raise NotImplementedError
