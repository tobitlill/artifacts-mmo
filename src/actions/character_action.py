from __future__ import annotations
import logging
from src.action import Action
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.character import Character


logger = logging.getLogger(__name__)


class CharacterNotFoundError(Exception):
    def __init__(self, character_name: str):
        self.character_name = character_name
        super().__init__(f"Character {character_name} not found")


class GetCharacter(Action):
    def __init__(self):
        self.name = "GetCharacterAction"
        super().__init__()

    async def execute(self, character: Character):
        logger.debug(f"Executing GetCharacterAction for {character.name}")
        characters = await self.client.get("/my/characters")
        for c in characters["data"]:
            if c["name"] == character.name:
                return c
        raise CharacterNotFoundError(character.name)
