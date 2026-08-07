import logging

from src.action import Action

logger = logging.getLogger(__name__)


class RestAction(Action):
    def __init__(self):
        self.name = "RestAction"
        super().__init__(name=self.name)

    async def execute(self, character):
        logger.info(f"{character.name} rests to recover HP")
        response = await self.client.post(f"/my/{character.name}/action/rest", {})

        self.apply_response_to_character(character, response)
        return response
