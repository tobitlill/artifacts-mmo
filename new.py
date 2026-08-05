import os
import logging
from dotenv import load_dotenv
from src.api_client import ArtifactsClient
from src.game import Game
from src.character import Character

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
client = ArtifactsClient(token=os.getenv("API_TOKEN"))


characters = [Character("tib0t"), Character("Hugo")]

game = Game(api_client=client, characters=characters)

while True:
    game.tick()
