import os
import logging
from abc import ABC
from dotenv import load_dotenv
from src.api_client import ArtifactsClient
from src.character import Character

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
client = ArtifactsClient(token=os.getenv("API_TOKEN"))


class Action(ABC):
    def __init__(self):
        self.name: str = ""

    def execute(self, character: Character):
        pass


class Move(Action):
    def __init__(self):
        self.name = "Move"
        super().__init__()

    def execute(self, character: Character):
        pass
