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


class FlakyGoal(Goal):
    """Simulates a permanently broken goal (bad item_code, an unhandled
    status code, ...) - every next_task() call fails."""

    def __init__(self):
        super().__init__("Flaky")
        self.attempts = 0

    def next_task(self, character):
        self.attempts += 1
        raise RuntimeError("boom")


def test_repeated_failures_trigger_backoff_skipping_ticks():
    client = FakeClient(["bad"])
    Action.configure_client(client)
    bad = Character("bad")
    goal = FlakyGoal()
    bad.goals.append(goal)
    game = Game(api_client=client, characters=[bad])
    run_async(game.start())

    run_async(game._tick_character_safe(bad))
    assert goal.attempts == 1
    assert bad.is_backing_off() is True

    # Backed off now - must skip actually ticking again, not retry
    # the same doomed goal every call.
    run_async(game._tick_character_safe(bad))
    assert goal.attempts == 1


def test_backoff_delay_grows_with_consecutive_failures():
    char = Character("A")
    assert char.record_tick_failure() == 2
    assert char.record_tick_failure() == 4
    assert char.record_tick_failure() == 8


def test_backoff_clears_after_a_successful_tick():
    char = Character("A")
    char.record_tick_failure()
    assert char.is_backing_off() is True

    char.record_tick_success()
    assert char.is_backing_off() is False


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
