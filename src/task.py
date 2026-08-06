from __future__ import annotations

from abc import ABC, abstractmethod
import logging
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.character import Character

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class Task(ABC):
    def __init__(self, name: str):
        self.name: str = name
        self.done: bool = False

    @abstractmethod
    def tick(self, character: Character):
        pass

    def is_on_cooldown(self, character: Character) -> bool:
        cooldown = character.get_cooldown()
        if cooldown > 0:
            logger.info(
                f"{character.name} is on cooldown for {cooldown} seconds, skipping {self.name}"
            )
            return True
        logger.info(f"{character.name} is not on cooldown, proceeding with {self.name}")
        return False
