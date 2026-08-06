from __future__ import annotations
import logging
import os

from dotenv import load_dotenv
from src.api_client import ArtifactsClient
from src.actions.character_action import GetCharacter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.character import Character

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
client = ArtifactsClient(token=os.getenv("API_TOKEN"))


class Inventory:
    def __init__(self, character: Character):
        self.character: Character = character
        self.slots: list[dict] = []
        self.max_items: int = 0

        self.update_inventory()

    def update_inventory(self):
        logger.debug(f"Updating inventory for character {self.character.name}")
        character_data = GetCharacter().execute(character=self.character)
        self.slots = character_data.get("inventory", [])
        self.max_items = character_data.get("inventory_max_items", 0)
        self.free_space = self.max_items - len(self.slots)

    def get_item_count(self, item_code: str) -> int:
        item_count = 0
        for slot in self.slots:
            if slot.get("code") == item_code:
                item_count += slot.get("quantity", 0)
        return item_count

    def get_free_space(self) -> int:
        item_count = 0
        for slot in self.slots:
            item_count += slot.get("quantity", 0)
        return self.max_items - item_count
