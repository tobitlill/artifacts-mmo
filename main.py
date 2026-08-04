import os
from dotenv import load_dotenv
from actions import move, fight, rest, gather, get_character, get_character_health

load_dotenv()

character_name = os.getenv("CHARACTER_NAME")

move(0, 1)

while True:
    health, max_health = get_character_health()
    if health < max_health * 0.5:
        rest()
    else:
        fight()

