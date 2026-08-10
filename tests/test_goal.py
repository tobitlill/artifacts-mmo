from src.action import Action
from src.character import Character
from src.goal import Goal
from src.goals.endless_fighting_goal import EndlessFightGoal
from src.goals.gather_resources_goal import GatherResourcesGoal
from src.location import Location

from conftest import FakeClient, run_async


class NeverStartsGoal(Goal):
    """next_task() returns None immediately - simulates a goal that's
    already satisfied on the very first tick."""

    def __init__(self):
        super().__init__("NeverStarts")

    def next_task(self, character):
        return None


def test_goal_with_no_next_task_marks_done_without_crashing():
    char = Character("A")
    goal = NeverStartsGoal()

    run_async(goal.tick(char))  # previously raised AttributeError on task.name

    assert goal.done is True


def test_goal_default_tasks_list_is_not_shared_between_instances():
    a = GatherResourcesGoal(location=Location(1, 1), item_code="wood", quantity=1)
    b = GatherResourcesGoal(location=Location(1, 1), item_code="wood", quantity=1)
    a.tasks.append("marker")
    assert b.tasks == [], "mutable default argument bug: goals must not share a tasks list"


def test_goal_instances_are_independent_across_characters():
    client = FakeClient(["A", "B"])
    Action.configure_client(client)

    char_a = Character("A")
    char_b = Character("B")
    run_async(char_a.refresh())
    run_async(char_b.refresh())

    char_a.goals.append(
        GatherResourcesGoal(location=Location(2, 2), item_code="sunflower", quantity=10)
    )
    char_b.goals.append(
        GatherResourcesGoal(location=Location(2, 2), item_code="sunflower", quantity=10)
    )

    for _ in range(20):
        run_async(char_a.tick())
        if char_a.cooldown > 0:
            client.expire_cooldown("A")
            char_a.set_cooldown_until(None)
        if char_a.goals and char_a.goals[0].done:
            break

    assert char_a.goals[0].done is True
    assert char_b.goals[0].done is False, (
        "finishing A's goal must not affect B's - they must be separate "
        "Goal instances, not one shared object"
    )


def test_fallback_goal_assigned_when_goal_queue_empties():
    client = FakeClient(["C"])
    Action.configure_client(client)

    char = Character(
        "C",
        fallback_goal_factory=lambda: EndlessFightGoal(monster="chicken", location=Location(5, 5)),
    )
    run_async(char.refresh())
    char.goals.append(
        GatherResourcesGoal(location=Location(2, 2), item_code="sunflower", quantity=10)
    )

    saw_fallback = False
    for _ in range(30):
        run_async(char.tick())
        if char.cooldown > 0:
            client.expire_cooldown("C")
            char.set_cooldown_until(None)
        if char.goals and isinstance(char.goals[0], EndlessFightGoal):
            saw_fallback = True
            break

    assert saw_fallback

    # EndlessFightGoal.next_task must resolve without crashing (hp_percent,
    # explicit location, FightTask all wired correctly).
    for _ in range(5):
        run_async(char.tick())
        if char.cooldown > 0:
            client.expire_cooldown("C")
            char.set_cooldown_until(None)


def test_no_fallback_leaves_character_idle_without_crashing():
    char = Character("A")
    assert char.fallback_goal_factory is None
    run_async(char.tick())  # goals empty, no fallback -> should just warn and return
