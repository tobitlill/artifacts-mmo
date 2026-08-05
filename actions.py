import os
import logging
from dotenv import load_dotenv
from src.api_client import ArtifactsClient, ArtifactsAPIError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
client = ArtifactsClient(token=os.getenv("API_TOKEN"))
character_name = os.getenv("CHARACTER_NAME")

CHARACTER_POS = None


def get_character(character_name: str) -> dict:
    logger.debug(f"Getting character {character_name}")
    characters = client.get("/my/characters")
    for c in characters["data"]:
        if c["name"] == character_name:
            return c
    raise Exception(f"Character {character_name} not found")


def get_character_position(character_name: str) -> tuple[int, int]:
    global CHARACTER_POS

    if not CHARACTER_POS:
        character = get_character(character_name)
        CHARACTER_POS = (character["x"], character["y"])

    return CHARACTER_POS


def get_character_health(character_name: str) -> tuple[int, int]:
    character = get_character(character_name)
    return character["hp"], character["max_hp"]


def get_inventory(character_name: str) -> tuple[list, int]:
    character_data = get_character(character_name)
    inventory_max_items = character_data.get("inventory_max_items")
    inventory_data = character_data.get("inventory")

    item_count = 0
    for slot in inventory_data:
        item_count += slot.get("quantity")

    # logger.info(f"Inventory data for {character_name}: {inventory_data}")
    # logger.info(f"Using {item_count} of {inventory_max_items} max items.")

    return inventory_data, inventory_max_items


def move(character_name: str, x: int, y: int):
    global CHARACTER_POS

    if get_character_position(character_name) == (x, y):
        logger.info(f"{character_name} is already at ({x}, {y})")
        return {"success": True, "message": "Character is already at the position"}

    try:
        client.post(f"/my/{character_name}/action/move", {"x": x, "y": y})
    except ArtifactsAPIError as e:
        if e.status_code == 490:
            pass
        else:
            raise e

    CHARACTER_POS = (x, y)
    logger.info(f"{character_name} moved to ({x}, {y})")


def fight(character_name: str):
    logger.info(f"Fighting {character_name}")
    return client.post(f"/my/{character_name}/action/fight", {})


def rest(character_name: str):
    logger.info(f"Resting {character_name}")
    return client.post(f"/my/{character_name}/action/rest", {})


def gather(character_name: str):
    logger.info(f"Gathering {character_name}")
    return client.post(f"/my/{character_name}/action/gathering", {})


def use(character_name: str, item_code: str, quantity: int = 1):
    logger.info(f"{character_name} is using {item_code}")
    return client.post(
        f"/my/{character_name}/action/use",
        {"code": item_code, "quantity": quantity},
    )
