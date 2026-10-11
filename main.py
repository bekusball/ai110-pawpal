"""Run a fixed PawPal+ demo with `python main.py`."""

from datetime import date, datetime, time, timedelta

from pawpal_system import Owner, Pet, Scheduler, Task


def build_demo_owner(available_minutes: int = 90) -> Owner:
    """Create two dogs and one cat with three, two, and one care tasks."""
    owner = Owner(name="Jordan", available_minutes=available_minutes)

    mochi = Pet(name="Mochi", species="dog")
    mochi.add_task(Task("Morning walk", 30, "high", "exercise"))
    mochi.add_task(Task("Feeding", 10, "high", "food"))
    mochi.add_task(Task("Brushing", 15, "low", "grooming"))

    biscuit = Pet(name="Biscuit", species="dog")
    biscuit.add_task(Task("Morning walk", 20, "high", "exercise"))
    biscuit.add_task(Task("Enrichment", 10, "medium", "enrichment"))

    luna = Pet(name="Luna", species="cat")
    luna.add_task(Task("Feeding", 5, "high", "food"))

    for pet in (mochi, biscuit, luna):
        owner.add_pet(pet)
    return owner


def _print_table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    """Align text columns to their contents and right-align minute counts."""
    widths = [max(len(value) for value in column) for column in zip(headers, *rows)]

    def format_row(values: tuple[str, ...]) -> str:
        return "  ".join(
            value.rjust(width) if header == "Min" else value.ljust(width)
            for header, value, width in zip(headers, values, widths)
        ).rstrip()

    print(format_row(headers))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print(format_row(row))


def main() -> None:
    """Print today's schedule table, brief task explanations, and skipped tasks."""
    # For the harder scenario, comment out the 90-minute line and uncomment
    # the 55-minute line. Tasks compete for the budget, not fixed clock times.
    owner = build_demo_owner(available_minutes=90)
    # owner = build_demo_owner(available_minutes=55)

    scheduler = Scheduler()
    plan = scheduler.build_daily_plan(owner)
    today = date.today()
    next_start = datetime.combine(today, time(hour=8))

    print(
        f"{owner.name}'s schedule | {today.isoformat()} | "
        f"Budget: {owner.available_minutes} min\n"
    )
    rows: list[tuple[str, ...]] = []
    for task in plan:
        end = next_start + timedelta(minutes=task.duration_minutes)
        rows.append((
            f"{next_start:%H:%M}-{end:%H:%M}",
            task.pet.name if task.pet else "-",
            task.title,
            str(task.duration_minutes),
            task.priority.upper(),
        ))
        next_start = end
    if rows:
        _print_table(("Time", "Pet", "Task", "Min", "Priority"), rows)
    else:
        print("No tasks scheduled.")

    used_minutes = sum(task.duration_minutes for task in plan)
    remaining_minutes = owner.available_minutes - used_minutes
    task_label = "task" if len(plan) == 1 else "tasks"
    print(
        f"\n{len(plan)} {task_label} | Used: {used_minutes} min | "
        f"Remaining: {remaining_minutes} min"
    )
    if plan:
        print("\nWhy these tasks:")
        for explanation in scheduler.explain_plan(plan, owner.available_minutes):
            print(f"  - {explanation}")

    selected_ids = {task.id for task in plan}
    skipped = [
        task
        for task in scheduler.sort_tasks(owner.get_all_tasks())
        if not task.completed and task.id not in selected_ids
    ]
    if skipped:
        print("\nSkipped (insufficient time):")
        _print_table(("Pet", "Task", "Min"), [
            (task.pet.name if task.pet else "-", task.title, str(task.duration_minutes))
            for task in skipped
        ])
    else:
        print("\nSkipped: none")


if __name__ == "__main__":
    main()
