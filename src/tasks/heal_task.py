from src.task import Task
from src.character import Character
from src.actions.rest_action import RestAction
from src.api_client import CharacterInCooldownError
from src.event_log import EVENT_LOG


class HealTask(Task):

    def __init__(self):
        super().__init__("HealTask")

    async def tick(self, character: Character):

        if self.is_on_cooldown(character):
            return

        try:
            await RestAction().execute(character)
        except CharacterInCooldownError as e:
            await self.apply_cooldown_error(character, e)
            return

        self.done = True
        EVENT_LOG.record(character.name, f"rested, hp now {character.hp_percent:.0f}%")
