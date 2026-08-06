from src.goal import Goal
from src.character import Character
from src.tasks.fight_task import FightTask
from src.tasks.heal_task import HealTask
from src.tasks.travel_task import TravelTask


class EndlessFightGoal(Goal):

    def __init__(self, monster: str):
        super().__init__("Endless Fighting")
        self.monster = monster

    def next_task(self, character: Character):

        if character.hp_percent < 40:
            return HealTask()

        if character.position != self.monster_location():
            return TravelTask(self.monster_location())

        return FightTask(self.monster)

