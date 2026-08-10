"""Named HTTP status codes returned by the Artifacts MMO API, used across
src/tasks/*.py to recognize specific expected-but-exceptional outcomes
(e.g. "inventory full") instead of comparing against bare numeric literals.
"""

ALREADY_THERE = 490  # e.g. move action: character is already at the destination
INSUFFICIENT_QUANTITY = 478  # not enough of an item on hand, or bank stock ran out
SKILL_LEVEL_TOO_LOW = 493  # character's skill level is below a recipe's requirement
INVENTORY_FULL = 497  # the action resolved server-side but its loot/output didn't fit
CHARACTER_ON_COOLDOWN = 499  # raised by ArtifactsClient as CharacterInCooldownError instead
CONTENT_NOT_FOUND = 598  # the monster/resource/bank isn't at this location after all
