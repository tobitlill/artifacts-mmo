from src.task import Task
from src.character import Character
from src.actions.fight_action import FightAction

class HealTask(Task):

    def __init__(self):
        super().__init__("HealTask")

    def tick(self, character: Character):

        if character.cooldown_active:
            return

        # Implement the logic to heal the character
        character.hp = min(character.max_hp, character.hp + 20)  # Example healing logic
        
        self.done = True