import actions
from src.goal import Goal
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class Character:
    def __init__(self, name: str, goals: list[Goal]):
        self.name = name
        self.goals = goals

        self.refresh()

    def refresh(self):
        data = actions.get_character(character_name=self.name)

        # set all attributes to the character class dynamically
        for key in data:
            setattr(self, key, data.get(key))

    def tick(self):
        if len(self.goals) > 0:
            self.goals[0].tick(self)
        else:
            logger.warning(f"No goal available for {self.name}")
            return
