from __future__ import annotations

from abc import ABC, abstractmethod
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from src.api_client import CharacterInCooldownError
from src.event_log import EVENT_LOG

if TYPE_CHECKING:
    from src.character import Character

logger = logging.getLogger(__name__)


class Task(ABC):
    def __init__(self, name: str):
        self.name: str = name
        self.done: bool = False

    @abstractmethod
    async def tick(self, character: Character):
        pass

    def is_on_cooldown(self, character: Character) -> bool:
        cooldown = character.cooldown
        if cooldown > 0:
            logger.info(
                f"{character.name} is on cooldown for {cooldown} seconds, skipping {self.name}"
            )
            return True
        logger.info(f"{character.name} is not on cooldown, proceeding with {self.name}")
        return False

    async def apply_cooldown_error(self, character: Character, e: CharacterInCooldownError) -> None:
        """The server rejected our action as still-on-cooldown despite our
        local check - our local cooldown clock is stale. Adopt the seconds
        the server told us; if it didn't tell us, fall back to a refresh()
        rather than guessing."""
        logger.warning(
            f"{character.name} was rejected as on-cooldown by the server while running {self.name}"
        )
        EVENT_LOG.record(character.name, f"cooldown mismatch on {self.name}, resyncing")
        if e.cooldown_seconds:
            character.set_cooldown_seconds(e.cooldown_seconds)
        else:
            await character.refresh()
