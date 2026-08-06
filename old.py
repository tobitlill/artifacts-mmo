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
    x, y = location
    move(character_name, x, y)
    health, max_health = get_character_health(character_name)
    inventory_data, inventory_max_items = get_inventory(character_name)
    has_chicken = False
    for slot in inventory_data:
        if slot["code"] == "cooked_chicken":
            has_chicken = True
            break

    if has_chicken and health < max_health - 80:
        use(character_name, "cooked_chicken")
    elif health < max_health * 0.6:
        rest(character_name)
    else:
        fight(character_name)


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

def gather_resources(character_name: str, location: tuple[int, int] = (0, 0)):
    x, y = location
    move(character_name, x, y)
    inventory_data, inventory_max_items = get_inventory(character_name)
    item_count = 0
    for slot in inventory_data:
        item_count += slot.get("quantity", 0)

    if item_count >= inventory_max_items:
        print(f"{character_name} inventory is full. Cannot gather more items.")
        return

    gather(character_name)


chicken_location = (0, 1)
green_slime_location = (0, -1)
ash_wood_location = (-1, 0)
sunflower_location = (2, 2)

while True:
    fight_monster("tib0t", green_slime_location)
    fight_monster("Hugo", chicken_location)
    gather_resources("Juergen", sunflower_location)
