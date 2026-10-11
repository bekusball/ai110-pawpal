"""Shared pytest fixtures for the PawPal+ test suite.

pytest imports this file automatically, so tests can request any fixture
defined here by name without importing anything.
"""

import pytest

from pawpal_system import Owner, Pet, Scheduler, Task


@pytest.fixture
def morning_walk() -> Task:
    return Task(
        title="Morning walk",
        duration_minutes=30,
        priority="high",
        category="exercise",
    )


@pytest.fixture
def feeding() -> Task:
    return Task(
        title="Feeding",
        duration_minutes=10,
        priority="high",
        category="food",
    )


@pytest.fixture
def nail_trim() -> Task:
    return Task(
        title="Nail trim",
        duration_minutes=15,
        priority="low",
        category="grooming",
    )


@pytest.fixture
def tasks(morning_walk: Task, feeding: Task, nail_trim: Task) -> list[Task]:
    """A deliberately unsorted mix of priorities and durations."""
    return [nail_trim, morning_walk, feeding]


@pytest.fixture
def pet() -> Pet:
    return Pet(name="Mochi", species="dog")


@pytest.fixture
def owner() -> Owner:
    return Owner(name="Jordan", available_minutes=45)


@pytest.fixture
def scheduler() -> Scheduler:
    return Scheduler()
