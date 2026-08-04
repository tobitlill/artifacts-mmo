import os
from dotenv import load_dotenv
from actions import move, fight, rest, gather, get_character, get_character_health

load_dotenv()

character_name = os.getenv("CHARACTER_NAME")


def endless_leveling():
    move(0, 1)
    while True:
        health, max_health = get_character_health()
        if health < max_health * 0.5:
            rest()
        else:
            fight()


def endless_copper_farming():
    move(2, 0)
    while True:
        gather()


endless_copper_farming()
