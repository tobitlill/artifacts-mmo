import logging

from src.action import Action

logger = logging.getLogger(__name__)


class FightAction(Action):
    def __init__(self, monster: str):
        self.name = "FightAction"
        self.monster = monster
        super().__init__(name=self.name)

    async def execute(self, character):
        logger.info(f"{character.name} fights against {self.monster}")
        response = await self.client.post(f"/my/{character.name}/action/fight", {})

        self.apply_response_to_character(character, response)
        return response
