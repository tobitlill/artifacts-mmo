from abc import ABC
from src.character import Character
from src.location import Location
import action
import logging

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

    def tick(self, character: Character):
        logger.info(f"Working on task {self}")


class CollectCopperTask(Task):
    def __init__(self):
        self.name = "CollectCopper"
        super().__init__(self.name)

    def tick(self, character: Character):
        """
        Go to (2, 0)
        """
        copper_location = Location(2, 0)

        action.Move(copper_location)

        pass
