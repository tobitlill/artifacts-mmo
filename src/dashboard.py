from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Group
from rich.panel import Panel
from rich.table import Table

from src.event_log import EVENT_LOG

if TYPE_CHECKING:
    from src.character import Character


def _cooldown_cell(seconds: int) -> str:
    if seconds <= 0:
        return "[green]ready[/]"
    style = "yellow" if seconds <= 3 else "red"
    return f"[{style}]{seconds}s[/]"


def _hp_cell(character: Character) -> str:
    percent = character.hp_percent
    style = "green" if percent >= 60 else "yellow" if percent >= 30 else "red"
    return f"[{style}]{character.hp}/{character.max_hp} ({percent:.0f}%)[/]"


def _current_goal_name(character: Character) -> str:
    return character.goals[0].name if character.goals else "-"


def _goal_progress(character: Character) -> str:
    if not character.goals:
        return "-"
    text = character.goals[0].progress_text(character)
    return text if text else "-"


def _current_task_name(character: Character) -> str:
    if not character.goals:
        return "-"
    tasks = character.goals[0].tasks
    return tasks[0].name if tasks else "-"


def _inventory_cell(character: Character) -> str:
    inventory = character.inventory
    used = inventory.max_items - inventory.get_free_space()
    return f"{used}/{inventory.max_items}"


def build_status_table(characters: list[Character]) -> Table:
    table = Table(title="Characters", expand=True)
    table.add_column("Character")
    table.add_column("Lvl", justify="right")
    table.add_column("Position")
    table.add_column("HP")
    table.add_column("Cooldown")
    table.add_column("Goal")
    table.add_column("Progress")
    table.add_column("Task")
    table.add_column("Inventory")

    for character in characters:
        table.add_row(
            character.name,
            str(character.data.get("level", "?")),
            f"({character.position.x}, {character.position.y})",
            _hp_cell(character),
            _cooldown_cell(character.cooldown),
            _current_goal_name(character),
            _goal_progress(character),
            _current_task_name(character),
            _inventory_cell(character),
        )

    return table


def build_events_panel() -> Panel:
    events = EVENT_LOG.recent()
    body = "\n".join(events) if events else "(no events yet)"
    return Panel(body, title="Recent Events", border_style="grey50")


def render(characters: list[Character]) -> Group:
    return Group(build_status_table(characters), build_events_panel())
