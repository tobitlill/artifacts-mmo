from src.task import Task
from src.character import Character
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class Goal:
    def __init__(self, name: str, tasks: list[Task]):
        self.name: str = name
        self.tasks: list[Task] = tasks
        self.done: bool = False

    def tick(self, character: Character):
        if self.done:
            logger.info(f"Goal {self} done for {character.name}")
            return

        if len(self.tasks) > 0:
            self.tasks[0].tick(character=character)
        else:
            self.done = True
            return
