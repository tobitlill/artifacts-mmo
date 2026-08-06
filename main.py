import os
import logging
from dotenv import load_dotenv
from src.api_client import ArtifactsClient
from src.game import Game
from src.character import Character
from src.goals.gather_ressources_goal import GatherResourcesGoal
from src.location import Location

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
client = ArtifactsClient(token=os.getenv("API_TOKEN"))


characters = [Character("tib0t"), Character("Hugo"), Character("Juergen")]
# characters = [Character("Juergen")]
gather_sunflowers_goal = GatherResourcesGoal(location=Location(2, 2), item_code="sunflower", quantity=100)

for character in characters:
    character.goals.append(gather_sunflowers_goal)

game = Game(api_client=client, characters=characters)

while True:
    game.tick()
