from __future__ import annotations

from abc import ABC, abstractmethod

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.character import Character
    from src.task import Task

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class Goal(ABC):
    def __init__(self, name: str, tasks: list[Task] = []):
        self.name: str = name
        self.tasks: list[Task] = tasks
        self.done: bool = False

    def tick(self, character: Character):
        if self.done:
            logger.info(f"Goal {self.name} done for {character.name}")
            return

        logger.debug(f"Ticking goal {self.name} for {character.name}")

        if not self.tasks:
            task = self.next_task(character)
            logger.info(f"Next task for goal {self.name} is {task.name}")

            if task is None:
                self.done = True
                return

            self.tasks.append(task)

        current_task = self.tasks[0]

        if current_task.done:
            logger.info(f"Task {current_task.name} done for goal {self.name}")
            self.tasks.pop(0)
            return

        logger.debug(f"Ticking current task {current_task.name} for goal {self.name}")
        current_task.tick(character)

        if current_task.done:
            logger.info(f"Task {current_task.name} done for goal {self.name}")
            self.tasks.pop(0)

    @abstractmethod
    def next_task(self, character: Character) -> Task | None:
        pass
