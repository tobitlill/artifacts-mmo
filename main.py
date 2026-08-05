import os
from dotenv import load_dotenv
from actions import (
    move,
    fight,
    rest,
    gather,
    get_character,
    get_character_health,
    use,
    get_inventory,
)

load_dotenv()

character_name = os.getenv("CHARACTER_NAME")


def fight_monster(character_name: str, location: tuple[int, int]):
    while True:
        x, y = location
        move(character_name, x, y)
        health, max_health = get_character_health()
        inventory_data, inventory_max_items = get_inventory()
        has_chicken = False
        for slot in inventory_data:
            if slot["code"] == "cooked_chicken":
                has_chicken = True
                break

        if has_chicken and health < max_health - 80:
            use("cooked_chicken")
        elif health < max_health * 0.3:
            rest()
        else:
            fight()


def collect_wood(character_name: str, location: tuple[int, int]):
    x, y = location
    move(character_name, x, y)
    gather(character_name)


def collect_copper(character_name: str):
    move(character_name, 2, 0)
    gather(character_name)


def collect_gudgeon(character_name: str):
    move(character_name, 4, 2)
    gather(character_name)


chicken_location = (0, 1)
green_slime_location = (0, -1)
ash_wood_location = (-1, 0)

while True:
    # fight_monster(green_slime_location)
    # collect_wood("Hugo", ash_wood_location)
    collect_wood("tib0t", ash_wood_location)
    collect_copper("Hugo")
