from __future__ import annotations

import logging
from abc import ABC
from typing import TYPE_CHECKING

from src.api_client import ArtifactsClient

if TYPE_CHECKING:
    from src.character import Character

logger = logging.getLogger(__name__)


class Action(ABC):
    """Base class for every API-backed action.

    A single ArtifactsClient is shared by all actions (one session, one
    place to eventually coordinate rate limiting) - it must be configured
    once via Action.configure_client() before any action executes.
    """

    client: ArtifactsClient | None = None

    @classmethod
    def configure_client(cls, client: ArtifactsClient) -> None:
        cls.client = client

    def __init__(self, name: str = ""):
        if Action.client is None:
            raise RuntimeError(
                "ArtifactsClient not configured - call Action.configure_client(client) first"
            )
        self.name: str = name
        self.client = Action.client

    async def execute(self, character: Character, **kwargs):
        pass

    def apply_response_to_character(self, character: Character, payload: object) -> None:
        """Update the character's local state (position, hp, inventory,
        cooldown, ...) directly from an action's own response instead of
        firing an extra GET to re-learn what the action itself just told us."""
        if not isinstance(payload, dict):
            return

        data = payload.get("data")
        if not isinstance(data, dict):
            return

        character_data = data.get("character")
        if isinstance(character_data, dict):
            character.apply_character_payload(character_data)

        # The cooldown block on the action response is the freshest source
        # of truth for this action; apply it last so it takes precedence
        # over whatever cooldown_expiration was embedded in character_data.
        cooldown_data = data.get("cooldown")
        if isinstance(cooldown_data, dict):
            character.set_cooldown_until(cooldown_data.get("expiration"))
