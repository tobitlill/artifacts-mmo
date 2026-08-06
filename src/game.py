from src.api_client import ArtifactsClient
from src.character import Character
import time
import math
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class Game:
    def __init__(self, api_client: ArtifactsClient, characters: list[Character]):
        self.api_client = api_client
        self.characters: list[Character] = characters

    def tick(self):
        logger.debug("Game Tick")
        for character in self.characters:
            character.tick()

        # wait until the next full second for the tick
        now = time.time()
        time.sleep(math.ceil(now) - now)
