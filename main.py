import asyncio
import os
import logging
from typing import Callable
from dotenv import load_dotenv
from rich.live import Live

from src.api_client import ArtifactsClient
from src.dashboard import render
from src.game import Game
from src.character import Character
from src.goal import Goal
from src.goals.endless_fighting_goal import EndlessFightGoal
from src.goals.gather_ressources_goal import GatherResourcesGoal
from src.location import Location
from src.logging_config import configure_logging
from src.constants import RESOURCE_LOCATIONS

configure_logging()
logger = logging.getLogger(__name__)

load_dotenv()

# One goal-list factory per character - each entry can be any sequence of
# Goal subclasses with whatever parameters they need (gathering, fighting,
# crafting, ...). Character only ever ticks goals[0], moving to goals[1]
# once it's done - so priority between multiple goals for the same
# character is just their order in the list: Juergen won't touch
# sunflower-stockpiling until the potion goal is fully done.
#
# GatherResourcesGoal figures out for itself (on its first tick) whether
# item_code needs crafting or can be gathered directly - no need to
# resolve a recipe or pass one in here.
#
# These are factories (callables), not Goal instances, so every character
# gets its own objects - Goal/Task state is mutable and per-run, so
# sharing one instance across characters would make their progress
# interfere with each other.
CHARACTER_GOALS: dict[str, Callable[[], list[Goal]]] = {
    "tib0t": lambda: [
        EndlessFightGoal(
            location=Location(1, -1),
            monster="red_slime",
            potion_item_code="small_health_potion",
            potion_slot="utility1",
            potion_min_level=5,
            max_potions=100,
        )
    ],
    "Hugo": lambda: [
        EndlessFightGoal(
            location=Location(0, -1),
            monster="chicken",
            potion_item_code="small_health_potion",
            potion_slot="utility1",
            potion_min_level=5,
            max_potions=100,
        )
    ],
    "Juergen": lambda: [
        GatherResourcesGoal(
            item_code="small_health_potion",
            quantity=1000,
            material_locations={"sunflower": RESOURCE_LOCATIONS["sunflower"]},
            cycle_batches=60,
        ),
        GatherResourcesGoal(
            item_code="sunflower",
            quantity=1000,
            location=RESOURCE_LOCATIONS["sunflower"],
        ),
        GatherResourcesGoal(
            item_code="gudgeon",
            quantity=1000,
            location=RESOURCE_LOCATIONS["gudgeon"],
        ),
    ],
    "Udo": lambda: [
        GatherResourcesGoal(
            item_code="copper_bar",
            quantity=200,
            material_locations={"copper_ore": RESOURCE_LOCATIONS["copper_ore"]},
        ),
        GatherResourcesGoal(
            location=RESOURCE_LOCATIONS["copper_ore"],
            item_code="copper_ore",
            quantity=2000,
        ),
    ],
    "Rolf": lambda: [
        GatherResourcesGoal(
            item_code="ash_plank",
            quantity=200,
            material_locations={"ash_wood": RESOURCE_LOCATIONS["ash_wood"]},
        ),
        GatherResourcesGoal(
            location=RESOURCE_LOCATIONS["ash_wood"], item_code="ash_wood", quantity=2000
        ),
    ],
    # Any character can instead get a fighting goal (or anything else) -
    # just swap its factory, e.g.:
    # "Rolf": lambda: [EndlessFightGoal(monster="chicken", location=Location(5, 5))],
}


async def main() -> None:
    client = ArtifactsClient(token=os.getenv("API_TOKEN"))

    characters = [Character(name) for name in CHARACTER_GOALS]

    for character in characters:
        character.goals.extend(CHARACTER_GOALS[character.name]())

    game = Game(api_client=client, characters=characters)

    try:
        with Live(render(characters), refresh_per_second=4, screen=False) as live:
            await game.start()
            live.update(render(characters))
            while True:
                await game.tick()
                live.update(render(characters))
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
