#!/usr/bin/env python3

"""
Minimal Artifacts MMO API Client

Features:
- Bearer authentication
- JSON requests
- Retry handling
- Rate limit handling
- Per-character cooldown handling
- Generic endpoint access
"""

from __future__ import annotations

import re
import time
import requests
from typing import Any, Dict


class ArtifactsAPIError(Exception):
    def __init__(
        self,
        status_code: int,
        message: str,
        data: Any = None,
    ):
        self.status_code = status_code
        self.message = message
        self.data = data

        super().__init__(f"[{status_code}] {message}")


class ArtifactsClient:

    BASE_URL = "https://api.artifactsmmo.com"

    def __init__(
        self,
        token: str,
        base_url: str | None = None,
        timeout: int = 30,
        max_retries: int = 5,
    ):
        self.base_url = base_url.rstrip("/") if base_url else self.BASE_URL

        self.timeout = timeout
        self.max_retries = max_retries

        self.session = requests.Session()

        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "artifacts-python-client/1.0",
            }
        )

        # character_name -> unix timestamp when next action is allowed
        self.cooldowns: dict[str, float] = {}

    # ---------------------------------------------------------
    # Public HTTP methods
    # ---------------------------------------------------------

    def get(
        self,
        path: str,
        params: Dict[str, Any] | None = None,
    ):
        return self.request(
            "GET",
            path,
            params=params,
        )

    def post(
        self,
        path: str,
        json: Dict[str, Any] | None = None,
    ):
        return self.request(
            "POST",
            path,
            json=json,
        )

    def patch(
        self,
        path: str,
        json: Dict[str, Any] | None = None,
    ):
        return self.request(
            "PATCH",
            path,
            json=json,
        )

    def delete(
        self,
        path: str,
        json: Dict[str, Any] | None = None,
    ):
        return self.request(
            "DELETE",
            path,
            json=json,
        )

    # ---------------------------------------------------------
    # Core request handler
    # ---------------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        **kwargs,
    ):

        character = self._extract_character(path)

        if character:
            self._wait_for_cooldown(character)

        url = self.base_url + path
        retries = 0

        while True:

            response = self.session.request(
                method,
                url,
                timeout=self.timeout,
                **kwargs,
            )

            try:
                data = response.json()
            except Exception:
                data = response.text

            # ---------------------------------------------
            # Success
            # ---------------------------------------------

            if response.ok or response.status_code == 499:

                if character:
                    self._update_cooldown(character, data.get("data"))

                return data

            # ---------------------------------------------
            # Rate limit / temporary errors
            # ---------------------------------------------

            if response.status_code in (
                429,
                500,
                502,
                503,
                504,
            ):

                if retries >= self.max_retries:
                    raise ArtifactsAPIError(
                        response.status_code,
                        "Maximum retries exceeded",
                        data,
                    )

                delay = self._retry_delay(
                    response,
                    retries,
                )

                time.sleep(delay)

                retries += 1
                continue

            # ---------------------------------------------
            # API errors
            # ---------------------------------------------

            message = data.get("error", {}).get("message") if isinstance(data, dict) else str(data)

            raise ArtifactsAPIError(
                response.status_code,
                message,
                data,
            )

    # ---------------------------------------------------------
    # Character cooldown handling
    # ---------------------------------------------------------

    def _extract_character(self, path: str) -> str | None:
        """
        Extract character name from paths like:

            /my/Bob/action/move
            /my/Alice/action/fight
        """
        match = re.match(r"^/my/([^/]+)/", path)
        if match:
            return match.group(1)
        return None

    def _wait_for_cooldown(self, character: str):
        until = self.cooldowns.get(character, 0)

        remaining = until - time.time()

        if remaining > 0:
            time.sleep(remaining)

    def _update_cooldown(
        self,
        character: str,
        data: Any,
    ):
        if not isinstance(data, dict):
            return

        cooldown = data.get("cooldown")

        if not cooldown:
            return

        remaining = cooldown.get("remaining_seconds") or cooldown.get("remaining")

        if not remaining:
            return

        self.cooldowns[character] = max(
            self.cooldowns.get(character, 0),
            time.time() + float(remaining),
        )

    # ---------------------------------------------------------
    # Retry calculation
    # ---------------------------------------------------------

    def _retry_delay(
        self,
        response,
        retry_number,
    ):

        retry_after = response.headers.get("Retry-After")

        if retry_after:
            return float(retry_after)

        # exponential backoff
        return min(
            2**retry_number,
            30,
        )
