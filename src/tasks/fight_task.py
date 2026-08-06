from src.task import Task
from src.character import Character
from src.actions.fight_action import FightAction

class FightTask(Task):

    def __init__(self, monster: str):
        super().__init__("FightTask")
        self.monster = monster

    def tick(self, character: Character):

        if character.cooldown_active:
            return

        FightAction(self.monster).execute(character)

        self.done = True