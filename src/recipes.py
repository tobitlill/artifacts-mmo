from __future__ import annotations

from dataclasses import dataclass

from src.actions.item_action import GetItemDetails


@dataclass(frozen=True)
class Recipe:
    item_code: str
    skill: str
    skill_level: int
    materials: dict[str, int]  # ingredient item_code -> quantity needed per batch
    yield_quantity: int  # crafted items produced per batch


async def try_resolve_recipe(item_code: str) -> Recipe | None:
    """Look up item_code's crafting recipe from the game's own item data,
    or None if it has none (a raw, directly-gatherable resource) - lets a
    caller auto-detect whether an item needs crafting instead of having to
    already know. See GatherResourcesGoal, which uses this via
    ResolveRecipeTask to figure this out for itself instead of requiring
    the recipe as a constructor argument."""
    data = await GetItemDetails(item_code).execute()
    craft = data.get("craft") or {}
    if not craft:
        return None

    materials = {m["code"]: m["quantity"] for m in craft.get("items", [])}
    return Recipe(
        item_code=item_code,
        skill=craft.get("skill", ""),
        skill_level=craft.get("level", 1),
        materials=materials,
        yield_quantity=craft.get("quantity", 1),
    )


async def resolve_recipe(item_code: str) -> Recipe:
    """Like try_resolve_recipe(), but raises if item_code turns out to have
    no crafting recipe - use when the caller already expects it to be
    craftable and wants a clear failure rather than a silent None."""
    recipe = await try_resolve_recipe(item_code)
    if recipe is None:
        raise ValueError(f"{item_code!r} has no crafting recipe")
    return recipe
