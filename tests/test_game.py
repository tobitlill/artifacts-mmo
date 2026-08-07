from src.action import Action
from src.character import Character
from src.game import Game
from src.goal import Goal

from conftest import FakeClient, run_async


class BuggyGoal(Goal):
    """Simulates a bug in one character's goal/task code - must not be
    allowed to take the other characters down with it."""

    def __init__(self):
        super().__init__("Buggy")

    def next_task(self, character):
        raise RuntimeError("boom")


class CountingGoal(Goal):
    def __init__(self):
        super().__init__("Counting")
        self.ticks = 0

    def next_task(self, character):
        self.ticks += 1
        return None  # immediately "done" each fresh assignment; we just want tick() called


def test_one_characters_exception_does_not_stop_the_others():
    client = FakeClient(["good", "bad"])
    Action.configure_client(client)

    good = Character("good")
    bad = Character("bad")
    counting_goal = CountingGoal()
    good.goals.append(counting_goal)
    bad.goals.append(BuggyGoal())

    game = Game(api_client=client, characters=[good, bad])
    run_async(game.start())

    # Directly exercise the per-character isolation wrapper (skip the
    # real-time sleep in tick()).
    run_async(game._tick_character_safe(good))
    run_async(game._tick_character_safe(bad))

    assert counting_goal.ticks == 1, "the healthy character must still have ticked normally"


def test_game_start_syncs_all_characters_concurrently():
    client = FakeClient(["A", "B", "C"])
    Action.configure_client(client)
    characters = [Character("A"), Character("B"), Character("C")]

    game = Game(api_client=client, characters=characters)
    run_async(game.start())

    for c in characters:
        assert c.data, f"{c.name} should have been refreshed by Game.start()"

    get_calls = [call for call in client.calls if call[0] == "GET"]
    assert len(get_calls) == 3
