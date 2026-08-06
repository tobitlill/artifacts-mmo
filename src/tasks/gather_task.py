from src.task import Task
from src.character import Character
from src.actions.gather_action import GatherAction
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GatherTask(Task):

    def __init__(self):
        super().__init__("GatherTask")

    def tick(self, character: Character):
        logger.info(f"Executing GatherTask for {character.name}")

        if self.is_on_cooldown(character):
            return

        GatherAction().execute(character)

        self.done = True
