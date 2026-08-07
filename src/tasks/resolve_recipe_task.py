from __future__ import annotations

from typing import Callable

from src.task import Task
from src.character import Character
from src.recipes import Recipe, try_resolve_recipe


class ResolveRecipeTask(Task):
    """A pure data lookup (no cooldown, no character mutation) that
    resolves item_code's crafting recipe - or None if it turns out to be
    a raw, non-craftable resource - and hands the result to a callback.
    Lets a Goal's otherwise-synchronous next_task() auto-detect whether an
    item needs crafting instead of being told upfront."""

    def __init__(self, item_code: str, on_result: Callable[[Recipe | None], None]):
        super().__init__("ResolveRecipeTask")
        self.item_code = item_code
        self.on_result = on_result

    async def tick(self, character: Character):
        recipe = await try_resolve_recipe(self.item_code)
        self.on_result(recipe)
        self.done = True
