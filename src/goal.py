from __future__ import annotations

from abc import ABC, abstractmethod

import logging
from typing import TYPE_CHECKING

from src.event_log import EVENT_LOG

if TYPE_CHECKING:
    from src.character import Character
    from src.task import Task

logger = logging.getLogger(__name__)


class Goal(ABC):
    def __init__(self, name: str, tasks: list[Task] | None = None):
        self.name: str = name
        self.tasks: list[Task] = tasks if tasks is not None else []
        self.done: bool = False

    async def tick(self, character: Character):
        if self.done:
            logger.info(f"Goal {self.name} done for {character.name}")
            return

        logger.debug(f"Ticking goal {self.name} for {character.name}")

        if not self.tasks:
            task = self.next_task(character)

            if task is None:
                logger.info(f"Goal {self.name} has no more tasks for {character.name}, marking done")
                self.done = True
                EVENT_LOG.record(character.name, f"goal completed: {self.name}")
                return

            logger.info(f"Next task for goal {self.name} is {task.name}")
            self.tasks.append(task)

        current_task = self.tasks[0]

        if current_task.done:
            logger.info(f"Task {current_task.name} done for goal {self.name}")
            self.tasks.pop(0)
            return

        logger.debug(f"Ticking current task {current_task.name} for goal {self.name}")
        await current_task.tick(character)

        if current_task.done:
            logger.info(f"Task {current_task.name} done for goal {self.name}")
            self.tasks.pop(0)

    @abstractmethod
    def next_task(self, character: Character) -> Task | None:
        pass

    def progress_text(self, character: Character) -> str | None:
        """Optional short human-readable progress indicator (e.g. "37/100
        sunflower") for display purposes. None means "not quantifiable" -
        e.g. an endless goal has no natural completion fraction."""
        return None
