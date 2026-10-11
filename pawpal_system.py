"""PawPal+ domain model and daily planner, matching diagrams/uml.mmd.

The model filters dated task occurrences, selects care tasks by priority and
time budget, and reports fixed-time conflicts. Interfaces display the plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from itertools import combinations
from uuid import uuid4


_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
_FREQUENCIES = ("daily", "once")


@dataclass
class Task:
    """One occurrence of a care activity, with 'daily' or 'once' frequency.

    Completed occurrences stay completed. Fixed start times are optional local
    clock times used for conflict reporting, independent of budget selection.
    """

    title: str
    duration_minutes: int
    priority: str
    category: str
    completed: bool = False
    frequency: str = "daily"
    pet: Pet | None = field(default=None, repr=False, compare=False)
    id: str = field(default_factory=lambda: str(uuid4()), init=False)
    due_date: date = field(default_factory=date.today)
    fixed_start_time: time | None = None

    def __post_init__(self) -> None:
        if type(self.duration_minutes) is not int or self.duration_minutes <= 0:
            raise ValueError("duration_minutes must be a positive integer")
        if self.priority not in _PRIORITY_ORDER:
            raise ValueError("priority must be high, medium, or low")
        if self.frequency not in _FREQUENCIES:
            raise ValueError("frequency must be daily or once")
        if type(self.due_date) is not date:
            raise ValueError("due_date must be a date")
        if self.fixed_start_time is not None and (
            type(self.fixed_start_time) is not time
            or self.fixed_start_time.tzinfo is not None
        ):
            raise ValueError("fixed_start_time must be a local time without a timezone")

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
    """Filter, complete, and plan care tasks, and report fixed-time conflicts."""

    def filter_tasks(
        self, tasks: list[Task], *, completed: bool | None = None,
        pet_name: str | None = None,
    ) -> list[Task]:
        """Return matching tasks in input order without copying or changing them.

        Supplied filters combine with AND. Pet names match exactly after
        trimming and case folding; matching names may belong to multiple pets.
        """
        name = pet_name.strip().casefold() if pet_name is not None else None
        filtered: list[Task] = []
        for task in tasks:
            if completed is not None and task.completed != completed:
                continue
            if name is not None and (
                task.pet is None or task.pet.name.strip().casefold() != name
            ):
                continue
            filtered.append(task)
        return filtered

    def mark_task_complete(
        self, owner: Owner, task_id: str, *, today: date | None = None,
    ) -> Task | None:
        """Complete an owner's occurrence and return its daily successor, if any.

        Daily successors are due one day after completion and attach to the
        same pet. One-time and already-completed tasks return None. Unknown
        IDs raise ValueError before changing the owner's tasks.
        """
        for pet in owner.pets:
            for task in pet.tasks:
                if task.id != task_id:
                    continue
                if task.completed:
                    return None
                successor = None
                if task.frequency == "daily":
                    completion_date = date.today() if today is None else today
                    successor = Task(
                        title=task.title,
                        duration_minutes=task.duration_minutes,
                        priority=task.priority,
                        category=task.category,
                        frequency=task.frequency,
                        due_date=completion_date + timedelta(days=1),
                        fixed_start_time=task.fixed_start_time,
                    )
                    pet.add_task(successor)
                task.completed = True
                return successor
        raise ValueError("task_id does not belong to this owner")

    def sort_tasks(self, tasks: list[Task]) -> list[Task]:
        """Return a new list ordered by priority, preserving order for ties."""
        return sorted(tasks, key=lambda task: _PRIORITY_ORDER[task.priority])

    def build_daily_plan(
        self, owner: Owner, *, plan_date: date | None = None,
    ) -> list[Task]:
        """Select incomplete tasks due by the planning date within the budget.

        Order high, medium, then low priority, keeping insertion order for ties.
        Include overdue tasks. Skip future tasks and tasks that do not fit,
        continuing to consider later tasks. Fixed times do not affect selection.
        """
        planning_date = date.today() if plan_date is None else plan_date
        remaining_minutes = owner.available_minutes
        plan: list[Task] = []
        pending = self.filter_tasks(owner.get_all_tasks(), completed=False)
        for task in self.sort_tasks(pending):
            if task.due_date <= planning_date and task.duration_minutes <= remaining_minutes:
                plan.append(task)
                remaining_minutes -= task.duration_minutes
        return plan

    def detect_conflicts(self, tasks: list[Task]) -> list[tuple[Task, Task]]:
        """Return each overlapping pair of incomplete fixed-time tasks once.

        Pass an owner's tasks to report clashes across all their pets. Compare
        full local date/time intervals so midnight crossings are handled and
        adjacent intervals do not conflict. Input order determines pair order.
        """
        intervals: list[tuple[Task, datetime, datetime]] = []
        seen_ids: set[str] = set()
        for task in self.filter_tasks(tasks, completed=False):
            if task.fixed_start_time is None or task.id in seen_ids:
                continue
            seen_ids.add(task.id)
            start = datetime.combine(task.due_date, task.fixed_start_time)
            intervals.append((task, start, start + timedelta(minutes=task.duration_minutes)))

        conflicts: list[tuple[Task, Task]] = []
        for first, second in combinations(intervals, 2):
            first_task, first_start, first_end = first
            second_task, second_start, second_end = second
            if first_start < second_end and second_start < first_end:
                conflicts.append((first_task, second_task))
        return conflicts

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
