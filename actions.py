import os
import logging
from dotenv import load_dotenv
from api_client import ArtifactsClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
client = ArtifactsClient(token=os.getenv("API_TOKEN"))
character_name = os.getenv("CHARACTER_NAME")

def get_character() -> dict:
    logger.debug(f"Getting character {character_name}")
    characters = client.get(f"/my/characters")
    for c in characters["data"]:
        if c["name"] == character_name:
            return c
    raise Exception(f"Character {character_name} not found")

def get_character_position() -> tuple[int, int]:
    character = get_character()
    return (character["x"], character["y"])

def get_character_health() -> tuple[int, int]:
    character = get_character()
    return character["hp"], character["max_hp"]

def move(x: int, y: int):
    logger.info(f"Moving {character_name} to ({x}, {y})")
    if get_character_position() == (x, y):
        return {"success": True, "message": "Character is already at the position"}
    return client.post(f"/my/{character_name}/action/move", {"x": x, "y": y})

def fight():
    logger.info(f"Fighting {character_name}")
    return client.post(f"/my/{character_name}/action/fight", {})

def rest():
    logger.info(f"Resting {character_name}")
    return client.post(f"/my/{character_name}/action/rest", {})

def gather():
    logger.info(f"Gathering {character_name}")
    return client.post(f"/my/{character_name}/action/gather", {})

