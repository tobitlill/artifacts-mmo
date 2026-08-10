from src.location import Location

BANK_LOCATION = Location(4, 1)

# Workshop map tiles, one per crafting skill - confirmed live via
# GET /maps?content_type=workshop. A recipe's required skill (from
# Recipe.skill, see src/recipes.py) indexes straight into this.
WORKSHOP_LOCATIONS: dict[str, Location] = {
    "woodcutting": Location(-2, -3),
    "cooking": Location(1, 1),
    "weaponcrafting": Location(2, 1),
    "gearcrafting": Location(3, 1),
    "jewelrycrafting": Location(1, 3),
    "alchemy": Location(2, 3),
    "mining": Location(1, 5),
}

RESOURCE_LOCATIONS: dict[str, Location] = {
    "sunflower": Location(2, 2),
    "copper_ore": Location(2, 0),
    "iron_ore": Location(1, 7),
    "ash_wood": Location(6, 1),
    "spruce_wood": Location(2, 6),
    "gudgeon": Location(4, 2),
}

MONSTER_LOCATIONS: dict[str, Location] = {
    "chicken": Location(0, 1),
    "green_slime": Location(0, -1),
    "red_slime": Location(1, -1),
    "yellow_slime": Location(4, -1),
    "blue_slime": Location(2, -1),
    "cow": Location(0, 2),
    "sheep": Location(5, 12),
}
