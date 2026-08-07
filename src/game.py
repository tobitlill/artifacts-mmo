from __future__ import annotations

import asyncio
import logging
import math
import time

from src.action import Action
from src.api_client import ArtifactsClient
from src.character import Character
from src.event_log import EVENT_LOG

logger = logging.getLogger(__name__)


class Game:
    def __init__(self, api_client: ArtifactsClient, characters: list[Character]):
        self.api_client = api_client
        self.characters: list[Character] = characters

        Action.configure_client(api_client)

    async def start(self) -> None:
        """Initial sync - run once before the first tick so every
        character's position/cooldown/inventory reflect real game state
        instead of the (0, 0)/empty constructor defaults."""
        await asyncio.gather(*(self._sync_character(c) for c in self.characters))

    async def _sync_character(self, character: Character) -> None:
        logger.info(f"Syncing initial state for {character.name}")
        await character.refresh()

    async def tick(self) -> None:
        logger.debug("Game Tick")

        # Tick every character concurrently instead of one after another -
        # a slow request or a cooldown-driven retry for one character no
        # longer blocks the others from acting in the same in-game second.
        await asyncio.gather(*(self._tick_character_safe(c) for c in self.characters))

        # wait until the next full second for the tick
        now = time.time()
        await asyncio.sleep(math.ceil(now) - now)

    async def _tick_character_safe(self, character: Character) -> None:
        """A bug or an unexpected API error for one character must never
        take the whole process down with it - isolate each character's
        tick so the others keep running."""
        try:
            await character.tick()
        except Exception as e:
            logger.exception(
                f"Unhandled error while ticking {character.name}, skipping this tick"
            )
            EVENT_LOG.record(character.name, f"ERROR: {e}")
